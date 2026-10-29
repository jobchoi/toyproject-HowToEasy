from pathlib import Path
import sys,tempfile,unittest
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from posting_tool.web import create_app


class SampleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.client=TestClient(create_app(Path(self.tmp.name)));self.addCleanup(self.client.close)
        self.headers={'X-Workspace-Token':self.client.get('/api/config').json()['token']}

    def test_four_distinct_styles_and_export_persistence(self):
        samples=self.client.get('/api/template-samples').json()['samples']
        self.assertEqual(len(samples),4);self.assertEqual(len({s['style'] for s in samples}),4)
        for sample in samples:
            result=self.client.post('/api/template-samples/'+sample['id'],json={},headers=self.headers).json()
            self.assertEqual(result['style'],sample['style'])
            restored=self.client.get('/api/previews/'+result['id']).json()
            self.assertEqual(restored['style'],sample['style'])
            html=self.client.get('/api/previews/'+result['id']+'/download/article.html').text
            self.assertIn('<style>',html);self.assertIn('default-src',html)
            self.assertIn('가상',result['warnings'][0])
            file_result=self.client.post('/api/previews',json={'files':[{'name':'sample.md','content':'# 제목\n\n내용'}],'template_id':sample['id']},headers=self.headers).json()
            self.assertEqual(file_result['style'],sample['style'])
            self.assertIn(sample['intro'],file_result['markdown'])
            saved=self.client.post('/api/templates/'+sample['id'],json={**sample,'name':'복제 샘플','clone':True},headers=self.headers).json()
            self.assertFalse(saved['builtin']);self.assertEqual(saved['style'],sample['style'])
        self.assertEqual(self.client.get('/api/templates/sample-editorial-v1').json()['name'],'01 에디토리얼 · 매거진')

    def test_invalid_style_is_rejected(self):
        for style in ('evil{}',{},None):
            response=self.client.post('/api/templates',json={'name':'x','intro':'','outro':'','sections':[],'style':style},headers=self.headers)
            self.assertEqual(response.status_code,400)
