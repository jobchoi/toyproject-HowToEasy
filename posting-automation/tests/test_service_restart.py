import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import manage_server as manager
from posting_deploy import save_json
import service_restart as restarting


class ScopedRestartTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()/'web-server'
        self.log=manager.Log(Path(self.tmp.name)/'logs');self.addCleanup(self.log.close)
        manager.apply(self.root,['posting-automation'],None,self.log)
        self.base=self.root/'posting-automation';(self.base/'compose.yaml').write_text('services: {}');(self.base/'.env').write_text('PRIVATE_ENV')
        data=manager.registry(self.root);data['projects']['posting-automation']['status']='migrated';save_json(self.root/'projects.json',data)
        self.calls=[];self.health='healthy';self.owner='posting-automation'

    def fake(self,args,log,code,**kwargs):
        self.calls.append((args,code))
        if code=='RESTART_STATUS':return json.dumps({'ID':'same-id','State':'running','Health':self.health})
        if code=='RESTART_OWNER':return json.dumps({'project':self.owner,'service':'web','files':str(self.base/'compose.yaml')})
        return ''

    def test_plan_does_not_restart_and_apply_is_scoped(self):
        with patch.object(restarting,'run',side_effect=self.fake):
            restarting.restart(self.root,'posting-automation',False,self.log)
            self.assertFalse(any(code=='SERVICE_RESTART' for _,code in self.calls))
            restarting.restart(self.root,'posting-automation',True,self.log)
        args=next(args for args,code in self.calls if code=='SERVICE_RESTART')
        self.assertEqual(args[-5:],['restart','--no-deps','--timeout','30','web'])
        self.assertNotIn('--build',args);self.assertNotIn('down',args)
        self.assertNotIn('PRIVATE_ENV',self.log.path.read_text())
        self.assertEqual(manager.registry(self.root)['projects']['posting-automation']['status'],'migrated')

    def test_wrong_owner_prevents_restart(self):
        self.owner='some-other-project'
        with patch.object(restarting,'run',side_effect=self.fake):
            with self.assertRaisesRegex(ValueError,'RESTART_OWNER'):restarting.restart(self.root,'posting-automation',True,self.log)
        self.assertFalse(any(code=='SERVICE_RESTART' for _,code in self.calls))

    def test_unhealthy_is_not_success_and_not_retried(self):
        self.health='unhealthy'
        with patch.object(restarting,'run',side_effect=self.fake):
            with self.assertRaisesRegex(ValueError,'RESTART_NOT_HEALTHY'):restarting.restart(self.root,'posting-automation',True,self.log)
        self.assertEqual(sum(code=='SERVICE_RESTART' for _,code in self.calls),1)
        self.assertEqual(manager.registry(self.root)['projects']['posting-automation']['restart_state'],'check_required')

    def test_global_or_unmigrated_restart_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'RESTART_PROJECT'):restarting.restart(self.root,'all',True,self.log)
        data=manager.registry(self.root);data['projects']['posting-automation']['status']='registered_not_migrated';save_json(self.root/'projects.json',data)
        with patch.object(restarting,'run',side_effect=self.fake):
            with self.assertRaisesRegex(ValueError,'RESTART_STATE'):restarting.restart(self.root,'posting-automation',True,self.log)
        self.assertFalse(self.calls)

    def test_doctor_detects_running_preserved_container(self):
        manager.apply(self.root,['filebrowser'],None,self.log)
        base=self.root/'filebrowser';(base/'compose.yaml').write_text('services: {}')
        data=manager.registry(self.root);data['projects']['filebrowser'].update(status='control_migrated_pending_review',control_state='switched_pending_review',preserved_container='file-service-before-test');save_json(self.root/'projects.json',data)
        from subprocess import CompletedProcess
        def docker(args,**kwargs):
            output='\n'.join(json.dumps(row) for row in [
                {'Names':'file-service','State':'exited','Status':'Exited (128)'},
                {'Names':'file-service-before-test','State':'running','Status':'Up (healthy)'}]) if 'ps' in args else 'Docker version'
            return CompletedProcess(args,0,output,'')
        with patch.object(manager.subprocess,'run',side_effect=docker),patch.object(manager.shutil,'which',return_value='/usr/bin/docker'):
            self.assertEqual(manager.check(self.root,self.log,doctor=True),1)
        output=self.log.path.read_text();self.assertIn('PRESERVED_RUNNING',output);self.assertIn('MANAGED_NOT_RUNNING',output)
