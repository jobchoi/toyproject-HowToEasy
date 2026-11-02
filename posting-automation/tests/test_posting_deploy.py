import importlib.util
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import manage_server as manager
import posting_deploy as deploy

class PostingDeployTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve(); self.root = self.base/'web-server'
        self.log = manager.Log(self.base/'logs'); self.addCleanup(self.log.close)
        self.source = self.base/'old-code'; self.source.mkdir()
        (self.source/'posting-automation'/'deploy').mkdir(parents=True)
        (self.source/'posting-automation'/'Dockerfile').write_text('FROM python:3.13-slim\n')
        (self.source/'posting-automation'/'deploy'/'compose.yaml').write_text('services: {}\n')
        (self.source/'.gitignore').write_text('posting-automation/.local/\n')
        for args in (['init','-q'],['add','.'],['-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','fixture']):
            subprocess.run(['git','-C',str(self.source),*args],check=True,capture_output=True)
        self.data = self.source/'posting-automation'/'.local'/'ui'; self.data.mkdir(parents=True)
        (self.data/'article.json').write_text('{"원고":"내용"}')
        manager.apply(self.root,['posting-automation'],None,self.log)
        records = manager.registry(self.root)
        records['projects']['posting-automation'].update(legacy_code=str(self.source),legacy_data=str(self.data))
        deploy.save_json(self.root/'projects.json',records)

    def prepare(self):
        with patch.object(deploy,'ensure_stopped'),patch.object(os,'getuid',return_value=1000):
            deploy.prepare(self.root,'test.ts.net',True,self.log)

    def test_prepare_copies_code_restores_backup_and_preserves_original(self):
        original = deploy.manifest(self.data)
        self.prepare()
        base = self.root/'posting-automation'
        self.assertEqual(deploy.manifest(base/'data'/'ui'),original)
        self.assertEqual(deploy.manifest(self.data),original)
        self.assertTrue((base/'repo'/'.git').is_dir())
        self.assertNotIn('POSTING_ALLOWED_HOSTS', (base/'compose.yaml').read_text())
        self.assertIn('test.ts.net',(base/'.env').read_text())
        self.assertEqual((base/'.env').stat().st_mode & 0o777,0o600)
        self.assertEqual(manager.registry(self.root)['projects']['posting-automation']['status'],'prepared_not_started')
        self.assertEqual(len(list((base/'backups').glob('*.tar.gz'))),1)
        self.assertIn('BACKUP_VERIFIED',self.log.path.read_text())
        self.prepare()  # Repeat never overwrites a differing dataset.
        (base/'data'/'ui'/'article.json').write_text('새 원고')
        with self.assertRaisesRegex(ValueError,'DATA_CONFLICT'): self.prepare()
        self.assertEqual((base/'data'/'ui'/'article.json').read_text(),'새 원고')

    def test_plan_busy_dirty_and_symlink_fail_before_copy(self):
        deploy.prepare(self.root,'test.ts.net',False,self.log)
        self.assertFalse((self.root/'posting-automation'/'.env').exists())
        with patch.object(deploy,'ensure_stopped',side_effect=ValueError('PORT_BUSY')),patch.object(os,'getuid',return_value=1000):
            with self.assertRaisesRegex(ValueError,'PORT_BUSY'): deploy.prepare(self.root,'test.ts.net',True,self.log)
        (self.source/'dirty.txt').write_text('미커밋')
        with self.assertRaisesRegex(ValueError,'SOURCE_DIRTY'): self.prepare()
        (self.source/'dirty.txt').unlink()
        (self.data/'link').symlink_to(self.base/'outside')
        with self.assertRaisesRegex(ValueError,'DATA_TYPE'): self.prepare()
        self.assertFalse((self.root/'posting-automation'/'repo'/'.git').exists())

    def test_lifecycle_is_scoped_and_review_required(self):
        self.prepare(); calls = []
        def fake(args,*unused,**kwargs):
            calls.append(args)
            if 'ps' in args:return json.dumps({'State':'running','Health':'healthy'})
            return ''
        with patch.object(deploy,'run',side_effect=fake),patch.object(deploy,'ensure_stopped'):
            deploy.operate(self.root,'start',self.log)
            self.assertEqual(manager.registry(self.root)['projects']['posting-automation']['status'],'running_pending_review')
            deploy.operate(self.root,'confirm',self.log)
            self.assertEqual(manager.registry(self.root)['projects']['posting-automation']['status'],'migrated')
            deploy.operate(self.root,'stop',self.log)
        for args in calls:
            self.assertIn('posting-automation',args)
            self.assertNotIn('--remove-orphans',args); self.assertNotIn('down',args)
            self.assertNotIn('prune',args)
        self.assertTrue((self.data/'article.json').exists())

    def test_backup_restore_failure_does_not_mark_prepared(self):
        with patch.object(deploy,'backup_and_verify',side_effect=ValueError('BACKUP_VERIFY')):
            with self.assertRaisesRegex(ValueError,'BACKUP_VERIFY'): self.prepare()
        self.assertEqual(manager.registry(self.root)['projects']['posting-automation']['status'],'registered_not_migrated')
        self.assertFalse((self.root/'posting-automation'/'compose.yaml').exists())

    def test_process_environment_cannot_override_prepared_data_path(self):
        with patch.dict(os.environ,{'POSTING_DATA_DIR':'/wrong/data','DOCKER_HOST':'tcp://wrong-host:2375'}):
            with patch.object(subprocess,'run',return_value=subprocess.CompletedProcess([],0,'','')) as execute:
                deploy.run(['docker','--context','default'],self.log,'TEST')
        actual = execute.call_args.kwargs['env']
        self.assertNotIn('POSTING_DATA_DIR',actual)
        self.assertNotIn('DOCKER_HOST',actual)

    def test_runtime_mutations_need_explicit_apply(self):
        script = Path(manager.__file__)
        result = subprocess.run([sys.executable,str(script),'--root',str(self.root),'--log-dir',str(self.base/'logs'),'posting','start'],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0)
        self.assertIn('DRY_RUN',result.stdout)
        self.assertEqual(manager.registry(self.root)['projects']['posting-automation']['status'],'registered_not_migrated')
