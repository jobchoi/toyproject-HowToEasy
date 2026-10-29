import json
from pathlib import Path
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from naver_trial_support import Journal, read_draft, comparable_text


class TrialTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_layout_lines_and_actual_changes(self):
        self.assertEqual(comparable_text('제목\n\n본문\n'), comparable_text('제목\n본문'))
        self.assertNotEqual(comparable_text('첫째\n둘째'), comparable_text('둘째\n첫째'))
        self.assertNotEqual(comparable_text('수치 100'), comparable_text('수치 10'))

    def test_invalid_contracts(self):
        path = self.root / 'draft.json'
        for data in ({'title':'x','body':''}, {'title':'x','body':'y','script':'x'}, {'title':1,'body':'x'}, []):
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                read_draft(path)
        path.write_text('x' * 256001)
        with self.assertRaises(ValueError):
            read_draft(path)

    def test_valid_unicode_and_blog_scoping(self):
        path = self.root / 'draft.json'
        data = {'title':'한글 제목','body':'본문\n두 번째 줄'}
        path.write_text(json.dumps(data), encoding='utf-8')
        self.assertEqual(read_draft(path), data)
        self.assertNotEqual(Journal.key('a',data), Journal.key('b',data))

    def test_concurrent_claim_and_restart_block(self):
        path = self.root / 'journal.db'
        journal = Journal(path)
        def claim(_):
            try:
                journal.claim('same')
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(sum(pool.map(claim, range(8))), 1)
        restarted = Journal(path)
        self.assertEqual(restarted.state('same'), 'save_requested')
        with self.assertRaises(ValueError):
            restarted.claim('same')
        restarted.finish('same','uncertain')
        with self.assertRaises(ValueError):
            restarted.claim('same')


if __name__ == '__main__':
    unittest.main()

class JournalPathTests(unittest.TestCase):
    def test_windows_uses_local_state_even_for_shared_project(self):
        from naver_trial_support import journal_path
        path = journal_path('//wsl.localhost/Ubuntu/project', platform='win32', environ={'LOCALAPPDATA': r'C:\Users\user\AppData\Local'})
        self.assertIn('HowToEasyPosting', str(path))
        self.assertNotIn('wsl.localhost', str(path))
        self.assertTrue(str(path).endswith('trials.sqlite3'))

    def test_windows_refuses_missing_or_shared_localappdata(self):
        from naver_trial_support import journal_path
        for local in ('', 'relative', r'\\server\share\state'):
            with self.assertRaises(ValueError):
                journal_path('/project', platform='win32', environ={'LOCALAPPDATA':local})

    def test_linux_keeps_existing_journal(self):
        from naver_trial_support import journal_path
        self.assertEqual(journal_path('/project', platform='linux'), Path('/project/.local/trials.sqlite3'))
