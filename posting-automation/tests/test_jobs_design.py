from pathlib import Path
import sys,tempfile,time,unittest
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from posting_tool.web import create_app
from posting_tool.jobs import Jobs,STAGES
from posting_tool.web_service import Workspace


class JobsDesignTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.client=TestClient(create_app(Path(self.tmp.name)));self.client.__enter__();self.addCleanup(self.client.__exit__,None,None,None)
        self.headers={'X-Workspace-Token':self.client.get('/api/config').json()['token']}

    def post(self,url,data):return self.client.post(url,json=data,headers=self.headers)

    def wait(self,key):
        for _ in range(200):
            result=self.client.get('/api/jobs/'+key).json()
            if result['state'] not in {'queued','running'}:return result
            time.sleep(.01)
        self.fail('job timed out')

    def test_actual_progress_and_failure_recovery(self):
        created=self.post('/api/jobs',{'text':'짧은 자료','title':'작업 시험'})
        self.assertEqual(created.status_code,202)
        result=self.wait(created.json()['id'])
        self.assertEqual(result['state'],'succeeded')
        self.assertEqual([s['name'] for s in result['stages']],STAGES)
        self.assertTrue(all(s['state']=='done' for s in result['stages']))
        self.assertEqual(self.client.get('/api/previews/'+result['result_id']).status_code,200)
        failed=self.wait(self.post('/api/jobs',{'text':''}).json()['id'])
        self.assertEqual(failed['state'],'failed');self.assertIn('평문',failed['error'])

    def test_live_choice_does_not_save_and_design_snapshot(self):
        before=self.client.get('/api/previews').json()
        preview=self.post('/api/template-choice-preview',{'template_id':'sample-briefing-v1','text':'실시간 미리보기'})
        self.assertEqual(preview.status_code,200);self.assertIn('#14252c',preview.json()['html'])
        self.assertEqual(before,self.client.get('/api/previews').json())
        spec={'name':'색상 시험','intro':'','outro':'','sections':[],'style':'plain','appearance':{'background':'#fff4e0','accent':'#123456','font':'serif','body_size':19,'line_height':2,'content_width':680,'paragraph_gap':24,'heading':'bar'}}
        template=self.post('/api/templates',spec).json()
        saved=self.post('/api/previews',{'text':'본문','template_id':template['id']}).json()
        self.assertEqual(saved['appearance'],spec['appearance']);self.assertIn('#fff4e0',saved['html'])
        self.assertIn('#fff4e0',self.client.get('/api/previews/'+saved['id']+'/download/article.html').text)
        for invalid in ({'accent':'red;url(http://x)'},{'font':{}},{'body_size':1000},{'line_height':True}):
            self.assertEqual(self.post('/api/templates',{**spec,'appearance':invalid}).status_code,400)

    def test_restart_marks_unfinished_job_without_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace=Workspace(Path(tmp));jobs=Jobs(workspace)
            key='a'*32;jobs.write({'id':key,'state':'running','stages':[]});jobs.close()
            restarted=Jobs(workspace)
            try:self.assertEqual(restarted.get(key)['state'],'interrupted')
            finally:restarted.close()
