from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from posting_tool.models import Article
from posting_tool.providers import builtin_registry,Capability,UnsupportedOperation
from posting_tool.providers.editor import TistoryEditorPublisher
from posting_tool.web import create_app
from fastapi.testclient import TestClient


class EditorDeliveryTests(unittest.TestCase):
    def test_tistory_module_is_inherited_and_never_claims_remote_save(self):
        article=Article('제목','# 제목\n\n<script>bad()</script>',(),())
        provider=builtin_registry().get('tistory-editor')
        with self.assertRaises(ValueError):provider.prepare_editor(article)
        package=provider.prepare_editor(article,reviewed=True)
        self.assertFalse(package.remote_saved);self.assertEqual(package.state,'prepared_for_editor')
        self.assertEqual(package.editor_url,'https://rt-jobchoi.tistory.com/manage/newpost')
        self.assertNotIn('<script>',package.html);self.assertIn('&lt;script&gt;',package.html)
        with self.assertRaises(UnsupportedOperation):provider.create_draft(article,reviewed=True)

    def test_images_become_explicit_attachment_reminders(self):
        article=Article('사진','![사진 설명](assets/'+'a'*64+'.png)\n사진 설명: 실제 캡션\n사진 출처: https://example.com/source',(),())
        package=TistoryEditorPublisher().prepare_editor(article,reviewed=True)
        self.assertNotIn('<img',package.html);self.assertIn('실제 캡션',package.html);self.assertIn('https://example.com/source',package.html)
        self.assertTrue(any('별도로 첨부' in text for text in package.warnings))

    def test_arbitrary_editor_targets_are_not_accepted(self):
        for url in ('http://rt-jobchoi.tistory.com','https://evil.example','https://rt-jobchoi.tistory.com@evil.example','https://rt-jobchoi.tistory.com:443','https://rt-jobchoi.tistory.com/manage'):
            with self.assertRaises(ValueError):TistoryEditorPublisher(url)

    def test_http_requires_token_and_review_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as folder, TestClient(create_app(Path(folder))) as client:
            headers={'X-Workspace-Token':client.get('/api/config').json()['token']}
            saved=client.post('/api/previews',headers=headers,json={'text':'확인한 원고입니다.','title':'기능 테스트'}).json()
            url='/api/previews/'+saved['id']+'/editor-package'
            self.assertEqual(client.post(url,json={'provider':'tistory-editor','reviewed':True}).status_code,403)
            self.assertEqual(client.post(url,headers=headers,json={'provider':'tistory-editor','reviewed':False}).status_code,400)
            self.assertEqual(client.post(url,headers=headers,json={'provider':'tistory-editor','reviewed':'true'}).status_code,400)
            self.assertEqual(client.post(url,headers=headers,json={'provider':'mock','reviewed':True}).status_code,400)
            response=client.post(url,headers=headers,json={'provider':'tistory-editor','reviewed':True})
            self.assertEqual(response.status_code,200,response.text)
            self.assertFalse(response.json()['remote_saved'])
            self.assertEqual(client.get('/api/previews/'+saved['id']).json()['markdown'],saved['markdown'])
            self.assertEqual(len(client.get('/api/platforms').json()['platforms']),2)
