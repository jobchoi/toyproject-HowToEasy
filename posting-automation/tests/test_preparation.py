import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from posting_tool.service import prepare_article
from posting_tool.exporting import export_article
from posting_tool.ingestion import import_sources
from posting_tool.providers import Publisher, Capability, ManualExportPublisher, MockPublisher, PublisherRegistry, UnsupportedOperation, DraftResult


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bundle = self.root / 'inbox' / 'sample'
        self.bundle.mkdir(parents=True)
        (self.bundle / 'a.md').write_text('# 제목\n\n## 내용\n<script>alert(1)</script>\n[링크](javascript:alert(2))\n', encoding='utf-8')

    def test_full_export_is_inert_and_source_unchanged(self):
        original = (self.bundle / 'a.md').read_bytes()
        article = prepare_article(self.root / 'inbox', 'sample')
        output = export_article(article, self.root / 'result', ManualExportPublisher())
        preview = (output / 'preview.html').read_text()
        self.assertNotIn('<script>', preview)
        self.assertNotIn('href="javascript:', preview)
        self.assertIn('&lt;script&gt;', preview)
        self.assertIn('Content-Security-Policy', preview)
        self.assertEqual((self.bundle / 'a.md').read_bytes(), original)
        self.assertEqual(json.loads((output / 'browser-draft.json').read_text())['title'], '제목')
        self.assertEqual(json.loads((output / 'article.json').read_text())['delivery'], 'export_only')
        self.assertTrue(article.warnings)
        with self.assertRaises(ValueError):
            export_article(article, output, ManualExportPublisher())
        self.assertEqual((output / 'preview.html').read_text(), preview)

    def test_import_bounds_and_links(self):
        for relative in ('../sample', '/etc'):
            with self.assertRaises(ValueError):
                import_sources(self.root / 'inbox', relative)
        (self.bundle / 'bad.md').symlink_to(self.bundle / 'a.md')
        with self.assertRaises(ValueError):
            import_sources(self.root / 'inbox', 'sample')
        (self.bundle / 'bad.md').unlink()
        (self.bundle / 'bad.md').write_bytes(b'\xff\xfe')
        with self.assertRaises(ValueError):
            import_sources(self.root / 'inbox', 'sample')
        (self.bundle / 'bad.md').write_bytes(b'a' * 256001)
        with self.assertRaises(ValueError):
            import_sources(self.root / 'inbox', 'sample')

    def test_subclass_registration_and_capability_boundaries(self):
        article = prepare_article(self.root / 'inbox', 'sample')
        with self.assertRaises(TypeError):
            Publisher()
        with self.assertRaises(UnsupportedOperation):
            ManualExportPublisher().create_draft(article, reviewed=True)
        with self.assertRaises(ValueError):
            MockPublisher().create_draft(article)
        self.assertTrue(MockPublisher().create_draft(article, reviewed=True).simulated)
        class CustomPublisher(Publisher):
            name = 'test-custom'
            capabilities = frozenset({Capability.CREATE_DRAFT})
            def _create_draft(self, article):
                return DraftResult(self.name, 'test-id', True)
        registry = PublisherRegistry()
        registry.register(CustomPublisher())
        self.assertEqual(registry.get('test-custom').create_draft(article, reviewed=True).remote_id, 'test-id')
        with self.assertRaises(ValueError):
            registry.register(CustomPublisher())
        with self.assertRaises(UnsupportedOperation):
            export_article(article, self.root / 'unsupported', registry.get('test-custom'))
