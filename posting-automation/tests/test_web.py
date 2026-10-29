from pathlib import Path
import sys
import tempfile
import unittest
from io import BytesIO
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from posting_tool.web import create_app


class WebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.client = TestClient(create_app(Path(self.tmp.name)))
        self.addCleanup(self.client.close)
        self.headers = {'X-Workspace-Token': self.client.get('/api/config').json()['token']}

    def test_upload_edit_restore_and_download(self):
        data = {'files':[{'name':'a.md','content':'# 한글 원고\n\n<script>alert(1)</script>'}]}
        result = self.client.post('/api/previews',json=data,headers=self.headers)
        self.assertEqual(result.status_code,200)
        saved = result.json()
        self.assertNotIn('<script>', saved['html'])
        self.assertIn('&lt;script&gt;',saved['html'])
        edited = self.client.post('/api/previews/'+saved['id'],json={'title':'수정 제목','markdown':'# 수정 원고\n\n내용'},headers=self.headers).json()
        self.assertNotEqual(saved['id'],edited['id'])
        self.assertEqual(self.client.get('/api/previews/'+saved['id']).json()['title'],'한글 원고')
        self.assertEqual(self.client.get('/api/previews/'+edited['id']).json()['title'],'수정 제목')
        response=self.client.get('/api/previews/'+edited['id']+'/download/bundle.zip')
        with ZipFile(BytesIO(response.content)) as bundle:
            self.assertIn('수정 원고',bundle.read('article.md').decode())
        self.assertEqual(self.client.get('/api/previews/'+edited['id']+'/download/secret').status_code,404)

    def test_roadmap_matches_checked_items(self):
        result = self.client.get('/api/roadmap')
        self.assertEqual(result.status_code,200)
        data = result.json()
        self.assertEqual(data['source'],'TASKS.md')
        self.assertEqual(data['done'],sum(item['done'] for section in data['sections'] for item in section['items']))
        self.assertGreater(data['total'],data['done'])

    def test_request_and_file_boundaries(self):
        payload={'files':[{'name':'../x.md','content':'test'}]}
        self.assertEqual(self.client.post('/api/previews',json=payload,headers=self.headers).status_code,400)
        self.assertEqual(self.client.post('/api/previews',json=payload).status_code,403)
        self.assertEqual(self.client.post('/api/previews',json=payload,headers={**self.headers,'Origin':'https://other.example'}).status_code,403)
        self.assertEqual(self.client.get('/',headers={'Host':'other.example'}).status_code,400)
        self.assertEqual(self.client.post('/api/previews',content=b'x'*1600001,headers=self.headers).status_code,413)
        payload={'files':[{'name':'x.md','content':'a'*256001}]}
        self.assertEqual(self.client.post('/api/previews',json=payload,headers=self.headers).status_code,400)
