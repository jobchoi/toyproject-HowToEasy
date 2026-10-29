"""Offline browser integration; run with RUN_BROWSER_TESTS=1 and installed Chromium."""
import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


@unittest.skipUnless(os.environ.get('RUN_BROWSER_TESTS') == '1', 'opt-in installed browser test')
class BrowserTrialTest(unittest.TestCase):
    def test_input_save_and_duplicate_block(self):
        import naver_browser_probe as probe
        from naver_trial_support import Journal, read_draft
        from playwright.sync_api import sync_playwright
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, channel='chromium')
            original = browser.new_context
            def local_context(**kwargs):
                context = original(**kwargs)
                context.route('**/*', lambda route: route.fulfill(content_type='text/html', body='''
                    <meta charset="utf-8"><div contenteditable="true" data-placeholder="제목"></div>
                    <div contenteditable="true" data-placeholder="본문"></div>
                    <button onclick="this.dataset.saved='yes'">임시저장</button>
                    <button onclick="throw new Error('must not publish')">발행</button>
                '''))
                return context
            manager = MagicMock()
            manager.__enter__.return_value = pw
            journal = Journal(Path(tmp) / 'trials.db')
            commands = iter(['editor', 'inspect', 'fill 0 1', 'INPUT', 'save', 'SAVE', 'save', 'SAVE', 'status', 'quit'])
            output = io.StringIO()
            with patch.object(probe, 'sync_playwright', return_value=manager), \
                 patch.object(pw.chromium, 'launch', return_value=browser), \
                 patch.object(browser, 'new_context', side_effect=local_context), \
                 patch.object(probe, 'configure_korean_fonts'), \
                 patch('naver_trial_support.Journal', return_value=journal), \
                 patch.object(sys, 'argv', ['probe', '--draft', str(root / 'examples/naver-trial.json')]), \
                 patch('builtins.input', side_effect=lambda _: next(commands)), \
                 contextlib.redirect_stdout(output):
                probe.main()
            draft = read_draft(root / 'examples/naver-trial.json')
            self.assertEqual(journal.state(journal.key('somnium_quest',draft)), 'needs_verification', output.getvalue())
            self.assertEqual(output.getvalue().count('저장 버튼을 눌렀습니다.'), 1)
            self.assertIn('이미 저장을 요청했습니다', output.getvalue())
