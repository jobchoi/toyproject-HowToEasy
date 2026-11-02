import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1]/'scripts/manage_server.py'
spec = importlib.util.spec_from_file_location('server_workspace',SCRIPT)
manager = importlib.util.module_from_spec(spec); spec.loader.exec_module(manager)

class WorkspaceManagementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve(); self.root = self.base/'web-server'
        self.logs = self.base/'logs'

    def run_cli(self,*args):
        return subprocess.run([sys.executable,str(SCRIPT),'--root',str(self.root),'--log-dir',str(self.logs),*args],capture_output=True,text=True,timeout=10)

    def test_plan_only_creates_logs_and_apply_preserves_existing_content(self):
        result = self.run_cli('init')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertFalse(self.root.exists()); self.assertIn('DRY_RUN',result.stdout)
        self.assertEqual(self.run_cli('init','--apply').returncode,0)
        registry = json.loads((self.root/'projects.json').read_text())
        self.assertEqual(set(registry['projects']),set(manager.DEFAULTS))
        for name in manager.DEFAULTS:
            self.assertTrue((self.root/name/'data').is_dir())
            self.assertEqual(list((self.root/name/'repo').iterdir()),[])
            self.assertFalse((self.root/name/'compose.yaml').exists())
        (self.root/'AGENTS.md').write_text('운영자가 보완한 지침')
        sample = self.root/'posting-automation'/'data'/'article.txt'; sample.write_text('보존할 원고')
        self.assertEqual(self.run_cli('init','--apply').returncode,0)
        self.assertEqual((self.root/'AGENTS.md').read_text(),'운영자가 보완한 지침')
        self.assertEqual(sample.read_text(),'보존할 원고')
        launcher = subprocess.run(['bash',str(self.root/'manage.sh'),'status'],capture_output=True,text=True,timeout=10)
        self.assertIn('[PROJECT] posting-automation',launcher.stdout)
        self.assertTrue((self.root/'logs').is_dir())
        self.assertEqual((self.root/'projects.json').stat().st_mode & 0o777,0o600)
        for log in self.logs.glob('*.jsonl'):
            self.assertEqual(log.stat().st_mode & 0o777,0o600)
            for line in log.read_text().splitlines(): self.assertIn('code',json.loads(line))

    def test_add_keeps_original_source_and_rejects_retarget(self):
        source = self.base/'legacy'; source.mkdir(); (source/'file').write_text('원본')
        result = self.run_cli('add','new-project','--source',str(source),'--apply')
        self.assertEqual(result.returncode,0,result.stdout)
        data = json.loads((self.root/'projects.json').read_text())
        self.assertEqual(data['projects']['new-project']['legacy_code'],str(source))
        self.assertEqual((source/'file').read_text(),'원본')
        self.assertEqual(self.run_cli('add','new-project','--source',str(self.base/'other'),'--apply').returncode,2)
        self.assertEqual(self.run_cli('add','../escape','--apply').returncode,2)
        self.assertFalse((self.base/'escape').exists())

    def test_symlink_and_existing_path_conflict_are_rejected(self):
        target = self.base/'target'; target.mkdir()
        self.root.symlink_to(target,target_is_directory=True)
        self.assertEqual(self.run_cli('init','--apply').returncode,2)
        self.assertEqual(list(target.iterdir()),[])
        self.root.unlink(); self.root.mkdir()
        (self.root/'duct-tape').mkdir(); (self.root/'duct-tape'/'data').write_text('파일 충돌')
        self.assertEqual(self.run_cli('init','--apply').returncode,2)
        self.assertFalse((self.root/'projects.json').exists())
        self.assertEqual((self.root/'duct-tape'/'data').read_text(),'파일 충돌')

    def test_concurrent_apply_is_blocked_without_modifying_registry(self):
        with manager.lock(self.root):
            result = self.run_cli('init','--apply')
        self.assertEqual(result.returncode,2)
        self.assertIn('다른 관리 작업',result.stdout)
        self.assertFalse((self.root/'projects.json').exists())

    def test_status_and_doctor_failures_are_logged_without_raw_command_output(self):
        self.assertEqual(self.run_cli('init','--apply').returncode,0)
        log = manager.Log(self.logs)
        payload = json.dumps({'Names':'file-service','State':'running','Status':'Up (unhealthy)','Command':'PASSWORD=SECRET','Env':['TOKEN=SECRET']})
        def fake(args,**kwargs):
            self.assertTrue(args in (['docker','--version'],['docker','compose','version'],['docker','ps','-a','--format','{{json .}}']))
            return subprocess.CompletedProcess(args,0,payload if args[1]=='ps' else 'version','PRIVATE STDERR')
        try:
            with patch.object(manager.subprocess,'run',side_effect=fake),patch.object(manager.shutil,'which',return_value='/bin/docker'):
                self.assertEqual(manager.check(self.root,log,doctor=True),1)
            with patch.object(manager.shutil,'which',return_value=None):
                self.assertEqual(manager.check(self.root,log,doctor=True),1)
        finally: log.close()
        text = log.path.read_text()
        self.assertIn('UNHEALTHY',text); self.assertIn('COMMAND_MISSING',text)
        self.assertNotIn('SECRET',text); self.assertNotIn('PRIVATE STDERR',text)

    def test_invalid_registry_is_not_overwritten(self):
        self.root.mkdir(); path = self.root/'projects.json'; path.write_text('{malformed')
        self.assertEqual(self.run_cli('init','--apply').returncode,2)
        self.assertEqual(path.read_text(),'{malformed')
        self.assertFalse((self.root/'posting-automation').exists())
        path.write_text('[]')
        self.assertEqual(self.run_cli('init','--apply').returncode,2)
        self.assertEqual(path.read_text(),'[]')
