from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import manage_server as manager
import posting_deploy as deploy
import filebrowser_repair as repair

class FilebrowserRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name).resolve(); self.root=self.path/'web-server'
        self.log=manager.Log(self.path/'logs'); self.addCleanup(self.log.close)
        manager.apply(self.root,['filebrowser'],None,self.log)
        self.legacy=self.path/'old'; self.legacy.mkdir()
        self.compose=self.legacy/'docker-compose.yml'; self.compose.write_text('PRIVATE ORIGINAL')
        self.settings=self.legacy/'settings.json'; self.settings.write_text('{"secret":"PRIVATE"}')
        self.db=self.legacy/'filebrowser.db'; self.db.write_bytes(b'DATABASE')
        data=manager.registry(self.root); data['projects']['filebrowser'].update(legacy_compose=str(self.compose))
        deploy.save_json(self.root/'projects.json',data)
        self.info={'image':'sha256:'+'a'*64,'health':'unhealthy','project':'my-server','service':'files',
                   'files':str(self.compose),'working_dir':str(self.legacy),'mounts':[
                    {'Type':'bind','Source':str(self.settings),'Destination':'/config/settings.json','RW':True},
                    {'Type':'bind','Source':str(self.db),'Destination':'/database/filebrowser.db','RW':True},
                    {'Type':'volume','Source':'/docker/anonymous','Destination':'/config','RW':True}]}
        self.model={'name':'my-server','services':{'files':{'image':'filebrowser/filebrowser:latest','healthcheck':{'test':['CMD-SHELL','/healthcheck.sh']},'volumes':[
            {'type':'bind','source':str(self.settings),'target':'/config/settings.json'},
            {'type':'bind','source':str(self.db),'target':'/database/filebrowser.db'},
            {'type':'volume','target':'/config'}]},'nginx':{'image':'nginx'}}}
        self.calls=[]

    def fake(self,args,log,code,**kwargs):
        self.calls.append((args,code))
        if code in {'BASE_CONFIG','OVERRIDE_CONFIG'}: return json.dumps(self.model)
        return ''

    def test_plan_no_mutations_and_scoped_apply_preserves_data(self):
        with patch.object(repair,'inspect',return_value=self.info),patch.object(repair,'run',side_effect=self.fake):
            repair.repair(self.root,False,self.log)
            self.assertFalse(self.calls)
            repair.repair(self.root,True,self.log)
        self.assertEqual(self.settings.read_text(),'{"secret":"PRIVATE"}')
        self.assertEqual(self.db.read_bytes(),b'DATABASE')
        override=json.loads((self.root/'filebrowser'/'health.override.json').read_text())
        self.assertEqual(override['services']['files']['healthcheck']['test'],repair.TEST)
        self.assertEqual(override['services']['files']['image'],self.info['image'])
        up=next(args for args,code in self.calls if code=='FILEBROWSER_RECREATE')
        self.assertIn('--no-deps',up); self.assertIn('--no-build',up); self.assertIn('never',up)
        self.assertEqual(up[-1],'files')
        self.assertFalse(any('down' in args or '--remove-orphans' in args or 'prune' in args for args,code in self.calls))
        values=manager.registry(self.root)['projects']['filebrowser']
        self.assertEqual(values['health_repair_state'],'healthy')
        backup=Path(values['health_backup']); self.assertEqual((backup/'filebrowser.db').read_bytes(),b'DATABASE')
        self.assertNotIn('PRIVATE',self.log.path.read_text())
        self.calls.clear()
        healthy={**self.info,'health':'healthy','files':str(self.compose)+','+values['health_override']}
        with patch.object(repair,'inspect',return_value=healthy),patch.object(repair,'run',side_effect=self.fake):
            repair.repair(self.root,True,self.log)
        self.assertFalse(any('stop' in args or 'up' in args for args,code in self.calls))

    def test_config_drift_aborts_before_stop(self):
        def drift(args,log,code,**kwargs):
            if code=='OVERRIDE_CONFIG':
                model=deepcopy(self.model); model['services']['nginx']['image']='different'; return json.dumps(model)
            return self.fake(args,log,code,**kwargs)
        with patch.object(repair,'inspect',return_value=self.info),patch.object(repair,'run',side_effect=drift):
            with self.assertRaisesRegex(ValueError,'UNEXPECTED_CONFIG'): repair.repair(self.root,True,self.log)
        self.assertFalse(any('stop' in args for args,code in self.calls))

    def test_apply_failure_preserves_backup_and_restarts_target_only(self):
        def fail(args,log,code,**kwargs):
            if code=='FILEBROWSER_RECREATE': raise ValueError('health failed')
            return self.fake(args,log,code,**kwargs)
        with patch.object(repair,'inspect',return_value=self.info),patch.object(repair,'run',side_effect=fail):
            with self.assertRaisesRegex(ValueError,'health failed'): repair.repair(self.root,True,self.log)
        self.assertEqual(manager.registry(self.root)['projects']['filebrowser']['health_repair_state'],'recovery_required')
        self.assertTrue(any(args==['docker','--context','default','start','file-service'] for args,code in self.calls))
        self.assertEqual(self.db.read_bytes(),b'DATABASE')

    def test_unexpected_project_is_rejected(self):
        wrong={**self.info,'project':'another-service'}
        with patch.object(repair,'inspect',return_value=wrong):
            with self.assertRaisesRegex(ValueError,'PROJECT_MISMATCH'): repair.repair(self.root,True,self.log)
