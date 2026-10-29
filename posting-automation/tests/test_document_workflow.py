from pathlib import Path
import sys
import tempfile
import unittest
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from posting_tool.web import create_app
from posting_tool.documents import from_plain, to_markdown


class DocumentWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.client=TestClient(create_app(Path(self.tmp.name)));self.addCleanup(self.client.close)
        self.headers={'X-Workspace-Token':self.client.get('/api/config').json()['token']}

    def post(self,path,data): return self.client.post(path,json=data,headers=self.headers)

    def test_plain_blocks_save_library_reopen_and_stale_guard(self):
        text='안녕하세요.\n\n1. 기본 정보\n서울에 대한 설명입니다.\n\n• 위치\n• 역사'
        response=self.post('/api/previews',{'text':text,'title':'평문 원고'})
        self.assertEqual(response.status_code,200,response.text);first=response.json()
        self.assertTrue(any(b['type']=='heading' for b in first['blocks']))
        self.assertTrue(any(b['type']=='list' for b in first['blocks']))
        blocks=first['blocks']+[{'type':'paragraph','text':'추가한 내용'}]
        edited=self.post('/api/previews/'+first['id'],{'title':'이어쓰기','blocks':blocks}).json()
        self.assertEqual(edited['article_id'],first['article_id'])
        self.assertEqual(edited['parent_id'],first['id'])
        latest=self.client.get('/api/previews').json()['articles']
        self.assertEqual(len(latest),1);self.assertEqual(latest[0]['id'],edited['id'])
        self.assertEqual(len(self.client.get('/api/previews?history=true').json()['articles']),2)
        self.assertIn('추가한 내용',self.client.get('/api/previews/'+edited['id']).json()['markdown'])
        stale=self.post('/api/previews/'+first['id'],{'title':'낡은 저장','blocks':blocks})
        self.assertEqual(stale.status_code,400)
        self.assertEqual(self.client.get('/api/previews/'+first['id']).json()['title'],'평문 원고')

    def test_template_create_preview_clone_version_and_apply_copy(self):
        spec={'name':'국가 소개','intro':'인사말','sections':['개요','교육','마무리'],'outro':'다음 글에서 만나요.'}
        preview=self.post('/api/template-preview',{'template':spec,'text':'테스트 원문'})
        self.assertEqual(preview.status_code,200)
        self.assertEqual(len(self.client.get('/api/templates').json()['templates']),5)
        first=self.post('/api/templates',spec).json()
        changed=self.post('/api/templates/'+first['id'],{**spec,'intro':'바뀐 인사말'}).json()
        self.assertNotEqual(first['id'],changed['id']);self.assertEqual(changed['version'],2)
        self.assertEqual(self.client.get('/api/templates/'+first['id']).json()['intro'],'인사말')
        clone=self.post('/api/templates/'+changed['id'],{**spec,'name':'복제','clone':True}).json()
        self.assertNotEqual(clone['family'],changed['family']);self.assertEqual(clone['version'],1)
        article=self.post('/api/previews',{'text':'평문 자료','title':'제목','template_id':changed['id']}).json()
        self.assertIn('바뀐 인사말',article['markdown']);self.assertIn('## 교육',article['markdown'])
        self.assertEqual(article['template_id'],changed['id'])
        copied=self.post('/api/previews/'+article['id']+'/template',{'template_id':clone['id']}).json()
        self.assertNotEqual(copied['article_id'],article['article_id'])
        self.assertEqual(self.client.get('/api/previews/'+article['id']).json()['template_id'],changed['id'])

    def test_bad_blocks_templates_and_script_are_inert(self):
        for blocks in ([{'type':'script','text':'x'}],[{'type':'heading','text':'a\nb'}],[]):
            from posting_tool.documents import validate_blocks
            with self.assertRaises(ValueError):validate_blocks(blocks)
        self.assertEqual(self.post('/api/previews',{'text':'x'*100001}).status_code,400)
        self.assertEqual(self.post('/api/templates',{'name':'x','intro':'','outro':'','sections':['x']*13}).status_code,400)
        result=self.post('/api/previews',{'text':'<script>alert(1)</script>','title':'테스트'}).json()
        self.assertNotIn('<script>',result['html'])
        self.assertIn('&lt;script&gt;',result['html'])
