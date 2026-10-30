import base64
from io import BytesIO
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile
from fastapi.testclient import TestClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from posting_tool.web import create_app
from posting_tool.documents import from_markdown, to_markdown

PNG = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jL1sAAAAASUVORK5CYII='

class MediaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.client = TestClient(create_app(Path(self.tmp.name))); self.addCleanup(self.client.close)
        self.headers = {'X-Workspace-Token':self.client.get('/api/config').json()['token']}

    def post(self, url, data):
        return self.client.post(url, json=data, headers=self.headers)

    def test_photo_survives_versions_template_and_exports(self):
        src = self.post('/api/media', {'content':PNG}).json()['src']
        self.assertEqual(src, self.post('/api/media', {'content':PNG}).json()['src'])
        first = self.post('/api/previews', {'text':'사진을 포함할 원고입니다.'}).json()
        photo = {'type':'image','text':'사진 대체 설명','src':src,'caption':'<script>캡션</script>','source':'https://example.com/photo?a=1&b=2'}
        md = to_markdown([photo]); self.assertEqual(from_markdown(md), [photo])
        saved = self.post('/api/previews/'+first['id'], {'title':first['title'],'blocks':[*first['blocks'],photo]}).json()
        self.assertNotIn('<script>캡션',saved['html']); self.assertIn('data:image/png;base64,',saved['html'])
        self.assertNotIn('data:image',self.client.get('/api/previews/'+first['id']).json()['html'])
        restored = self.client.get('/api/previews/'+saved['id']).json()
        self.assertEqual(restored['blocks'][-1],photo)
        choice = self.post('/api/template-choice-preview', {'template_id':'sample-editorial-v1','markdown':md})
        self.assertEqual(choice.status_code,200); self.assertIn('data:image/png',choice.json()['html'])
        applied = self.post('/api/previews/'+saved['id']+'/template',{'template_id':'sample-editorial-v1'}).json()
        self.assertIn('data:image/png',applied['html'])
        package = self.client.get('/api/previews/'+saved['id']+'/download/bundle.zip')
        with ZipFile(BytesIO(package.content)) as archive:
            self.assertEqual(archive.read(src),base64.b64decode(PNG))
            self.assertIn(src,archive.read('article.md').decode())
            self.assertIn('data:image/png',archive.read('article.html').decode())

    def test_invalid_media_missing_files_and_unsafe_sources(self):
        for content in ('bad',base64.b64encode(b'<svg onload="evil()"/>').decode(), 'a'*960001):
            self.assertEqual(self.post('/api/media',{'content':content}).status_code,400)
        article = self.post('/api/previews',{'text':'원고'}).json()
        photo = {'type':'image','text':'사진','src':'assets/'+'a'*64+'.png','caption':'','source':''}
        self.assertEqual(self.post('/api/previews/'+article['id'],{'title':'원고','blocks':[photo]}).status_code,400)
        src = self.post('/api/media',{'content':PNG}).json()['src']
        for field,value in [('src','../../etc/passwd'),('source','javascript:alert(1)'),('text','](bad)'),('caption','줄\n바꿈')]:
            invalid = {**photo,'src':src,field:value}
            self.assertEqual(self.post('/api/previews/'+article['id'],{'title':'원고','blocks':[invalid]}).status_code,400)
        self.assertEqual(self.client.post('/api/media',json={'content':PNG}).status_code,403)
