from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from posting_tool.progress import read_roadmap


class ProgressTests(unittest.TestCase):
    def test_markdown_status_is_not_inferred_from_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'TASKS.md'
            path.write_text('# 작업\n## 첫 단계\n1. [x] 모의 구현\n- [ ] 실제 연결 미검증\n   - [X] 문서 작성\n## 빈 항목\n설명\n## 다음\n- [ ] 다음 구현\n',encoding='utf-8')
            result=read_roadmap(path)
            self.assertEqual(result['done'],2)
            self.assertEqual(result['total'],4)
            self.assertEqual(len(result['sections']),2)
            self.assertFalse(result['sections'][0]['items'][1]['done'])
