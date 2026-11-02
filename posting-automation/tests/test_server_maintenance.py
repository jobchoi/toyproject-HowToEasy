import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import manage_server as manager
import posting_deploy as deploy
import server_maintenance as maintenance

class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name).resolve(); self.root = self.path/'web-server'
        self.log = manager.Log(self.path/'logs'); self.addCleanup(self.log.close)
        manager.apply(self.root,['posting-automation'],None,self.log)
        self.base = self.root/'posting-automation'; (self.base/'data'/'ui').mkdir()
        (self.base/'data'/'ui'/'article.txt').write_text('현재 수정한 글')
        records = manager.registry(self.root); records['projects']['posting-automation']['status']='migrated'
        deploy.save_json(self.root/'projects.json',records)
        self.command = ['docker','--context','default','compose','-p','posting-automation']

    def fake_run(self,args,log,code,**kwargs):
        self.calls.append(args)
        if code=='BACKUP_STATUS': return '{"State":"running"}'
        if code=='BACKUP_CODE': return 'commit-test'
        return ''

    def test_running_backup_preserves_current_data_and_resumes(self):
        self.calls = []; records = manager.registry(self.root)
        with patch.object(maintenance,'run',side_effect=self.fake_run),patch.object(maintenance,'ensure_stopped'):
            maintenance.backup_locked(self.root,self.base,self.command,records,self.log)
        after = manager.registry(self.root)['projects']['posting-automation']
        self.assertEqual(after['status'],'migrated')
        self.assertTrue(Path(after['last_backup']).is_file())
        self.assertTrue(Path(after['last_backup']+'.json').is_file())
        self.assertEqual((self.base/'data'/'ui'/'article.txt').read_text(),'현재 수정한 글')
        self.assertTrue(any('stop' in args for args in self.calls))
        self.assertTrue(any('--no-build' in args for args in self.calls))
        self.assertNotIn('down',str(self.calls)); self.assertNotIn('prune',str(self.calls))

    def test_backup_error_resumes_and_resume_error_records_recovery(self):
        self.calls = []; records=manager.registry(self.root)
        with patch.object(maintenance,'run',side_effect=self.fake_run),patch.object(maintenance,'ensure_stopped'),patch.object(maintenance,'backup_and_verify',side_effect=ValueError('verification failed')):
            with self.assertRaisesRegex(ValueError,'verification'): maintenance.backup_locked(self.root,self.base,self.command,records,self.log)
        self.assertTrue(any('--no-build' in args for args in self.calls))
        self.assertNotIn('last_backup',manager.registry(self.root)['projects']['posting-automation'])
        def fail_resume(args,log,code,**kwargs):
            if code=='BACKUP_RESUME': raise ValueError('restart failed')
            return self.fake_run(args,log,code,**kwargs)
        with patch.object(maintenance,'run',side_effect=fail_resume),patch.object(maintenance,'ensure_stopped'):
            with self.assertRaisesRegex(ValueError,'restart'): maintenance.backup_locked(self.root,self.base,self.command,records,self.log)
        self.assertEqual(manager.registry(self.root)['projects']['posting-automation']['status'],'recovery_required')

    def test_stopped_backup_does_not_start_service(self):
        def stopped(args,log,code,**kwargs):
            self.calls.append(args)
            return '{"State":"exited"}' if code=='BACKUP_STATUS' else 'commit'
        self.calls=[]
        with patch.object(maintenance,'run',side_effect=stopped),patch.object(maintenance,'ensure_stopped'):
            maintenance.backup_locked(self.root,self.base,self.command,manager.registry(self.root),self.log)
        self.assertFalse(any('stop' in args or 'up' in args for args in self.calls))

    def test_handoff_preserves_old_launcher_and_requires_complete_code(self):
        managed = self.base/'repo'/'posting-automation'/'scripts'; managed.mkdir(parents=True)
        before=(self.root/'manage.sh').read_text()
        with self.assertRaisesRegex(ValueError,'MANAGER_MISSING'): maintenance.use_managed(self.root,True,self.log)
        for name in ('manage_server.py','posting_deploy.py','server_maintenance.py'):
            shutil.copyfile(Path(manager.__file__).parent/name,managed/name)
        with patch.object(maintenance,'run',return_value=''):
            maintenance.use_managed(self.root,False,self.log)
            self.assertEqual((self.root/'manage.sh').read_text(),before)
            maintenance.use_managed(self.root,True,self.log)
        self.assertIn(str(managed/'manage_server.py'),(self.root/'manage.sh').read_text())
        self.assertEqual(next(self.root.glob('manage.sh.before-*')).read_text(),before)
        subprocess.run(['bash','-n',str(self.root/'manage.sh')],check=True)

    def test_health_diagnostic_does_not_disclose_command_args_or_raw_errors(self):
        payload={'image':'filebrowser/filebrowser:latest','health':'unhealthy','streak':5,
                 'test':['CMD-SHELL','wget http://user:password@localhost/?token=SECRET'],
                 'checks':[{'start':'a','end':'b','exit_code':127}]}
        with patch.object(maintenance,'run',return_value=json.dumps(payload)) as execute:
            maintenance.diagnose_filebrowser(self.log)
        text=self.log.path.read_text()
        self.assertNotIn('password',text); self.assertNotIn('SECRET',text)
        self.assertIn('wget',text); self.assertIn('127',text)
        self.assertNotIn('.Output',execute.call_args.args[0][-2])

    def test_archive_format_errors_use_managed_error_path(self):
        import tarfile
        with patch.object(deploy.tarfile,'open',side_effect=tarfile.ReadError('private raw error')):
            with self.assertRaisesRegex(ValueError,'BACKUP_FORMAT'):
                deploy.backup_and_verify(self.base/'data'/'ui',self.base/'backups'/'failed.tar.gz',{},self.log)
