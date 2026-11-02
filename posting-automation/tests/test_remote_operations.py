import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import remote_job as job
import remote_server as remote

STUB = '''import argparse,json,uuid
from pathlib import Path
p=argparse.ArgumentParser(description='status posting doctor repair-filebrowser diagnose-filebrowser');p.add_argument('--root');p.add_argument('--log-dir');a,rest=p.parse_known_args()
root=Path(a.root)
with (root/'calls.jsonl').open('a') as f:f.write(json.dumps(rest)+'\\n')
logs=Path(a.log_dir);logs.mkdir(exist_ok=True)
path=logs/(uuid.uuid4().hex+'.jsonl');path.write_text('{"code":"TEST_OK"}\\n')
print('로그: '+str(path));print('[TEST_OK] safe output')
'''

class RemoteOperationsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name).resolve();self.root=self.base/'web-server';self.repo=self.root/'posting-automation'/'repo'
        script=self.repo/'posting-automation'/'scripts'/'manage_server.py';script.parent.mkdir(parents=True);script.write_text(STUB)
        (self.root/'projects.json').write_text('{"schema_version":1}')
        for args in (['init','-q','--initial-branch=develop'],['add','.'],['-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','fixture']):
            subprocess.run(['git','-C',str(self.repo),*args],check=True,capture_output=True)

    def test_remote_worker_collects_results_and_never_repeats_job(self):
        identifier=uuid4().hex
        result=job.run(self.root,identifier,'repair-filebrowser',True)
        self.assertEqual(result['state'],'succeeded')
        calls=(self.root/'calls.jsonl').read_text().splitlines()
        self.assertEqual(json.loads(calls[0]),['repair-filebrowser','--apply'])
        self.assertTrue(result['management_logs']);self.assertIn('safe output',result['console'])
        job.run(self.root,identifier,'repair-filebrowser',True)
        self.assertEqual((self.root/'calls.jsonl').read_text().splitlines(),calls)
        with self.assertRaisesRegex(ValueError,'JOB_ID_CONFLICT'):job.run(self.root,identifier,'status')
        self.assertEqual(job.run(self.root,identifier,'status',collect=True)['state'],'succeeded')

    def test_dry_run_unknown_and_symlink_job_paths(self):
        identifier=uuid4().hex;job.run(self.root,identifier,'posting-backup',False)
        self.assertNotIn('--apply',(self.root/'calls.jsonl').read_text())
        orphan=self.root/'remote-runs'/uuid4().hex;orphan.mkdir()
        (orphan/'request.json').write_text(json.dumps({'pid':99999999,'process_marker':'not-alive','workflow':'posting-backup','apply':True,'sync':False}))
        self.assertEqual(job.collected(orphan)['state'],'unknown')
        self.assertEqual(job.run(self.root,orphan.name,'posting-backup',True)['state'],'unknown')
        escape=self.root/'remote-runs'/uuid4().hex;escape.symlink_to(self.base,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'UNSAFE_PATH'):job.run(self.root,escape.name,'status')

    def test_daemon_payload_entrypoint_produces_report(self):
        identifier=uuid4().hex
        result=subprocess.run([sys.executable,'-u','-','--root',str(self.root),'--job-id',identifier,'--workflow','status'],input=Path(job.__file__).read_text(),capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['state'],'succeeded')
        self.assertTrue((self.root/'remote-runs'/identifier/'result.json').is_file())

    def test_ssh_arguments_reject_option_injection_and_quote_remote_paths(self):
        with self.assertRaises(ValueError):remote.ssh_command('-oProxyCommand=evil',22,'~/web-server',uuid4().hex,'status',False,False,False)
        command=remote.ssh_command('pi-alias',22,"~/web server/$(touch BAD)",uuid4().hex,'status',False,False,False)
        self.assertIn('BatchMode=yes',command);self.assertIn('StrictHostKeyChecking=yes',command)
        self.assertIn("'~/web server/$(touch BAD)'",command[-1])

    def test_local_report_collection_and_transport_failure(self):
        result={'job_id':'a'*32,'state':'failed','exit_code':2,'console':'[ERROR] test','management_logs':[{'name':'safe.jsonl','text':'{"code":"ERROR"}\n'}]}
        output=self.base/'local-result'
        argv=['remote_server.py','--host','pi-alias','--job-id','a'*32,'--output',str(output)]
        with patch.object(sys,'argv',argv),patch.object(remote.subprocess,'run',return_value=subprocess.CompletedProcess([],0,json.dumps(result),'')):
            self.assertEqual(remote.main(),2)
        self.assertTrue((output/'report.md').is_file());self.assertTrue((output/'remote-safe.jsonl').is_file())
        failed=self.base/'auth-result'
        with patch.object(sys,'argv',['remote_server.py','--host','pi-alias','--output',str(failed)]),patch.object(remote.subprocess,'run',return_value=subprocess.CompletedProcess([],255,'','Permission denied (publickey). PRIVATE-TOKEN')):
            self.assertEqual(remote.main(),2)
        self.assertEqual(json.loads((failed/'result.json').read_text())['state'],'connection_failed')
        self.assertNotIn('PRIVATE-TOKEN',(failed/'ssh.stderr.txt').read_text())
        self.assertEqual((failed/'report.md').stat().st_mode & 0o777,0o600)

    def test_disconnect_does_not_kill_detached_worker(self):
        import time
        script=self.repo/'posting-automation'/'scripts'/'manage_server.py'
        script.write_text(STUB.replace('root=Path(a.root)','root=Path(a.root)\nimport time; time.sleep(0.5)'))
        identifier=uuid4().hex
        process=subprocess.Popen([sys.executable,str(Path(job.__file__)),'--root',str(self.root),'--job-id',identifier,'--workflow','status'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        folder=self.root/'remote-runs'/identifier
        try:
            deadline=time.monotonic()+5
            while not (folder/'request.json').exists() and time.monotonic()<deadline:time.sleep(0.05)
            self.assertTrue((folder/'request.json').exists())
            process.terminate();process.wait(timeout=3)
            deadline=time.monotonic()+6
            while not (folder/'result.json').exists() and time.monotonic()<deadline:time.sleep(0.05)
            self.assertEqual(job.collected(folder)['state'],'succeeded')
        finally:
            if process.poll() is None:process.kill();process.wait()

    def test_dirty_remote_repository_aborts_before_management(self):
        (self.repo/'dirty.txt').write_text('보존할 변경')
        identifier=uuid4().hex
        result=job.run(self.root,identifier,'posting-backup',True,sync=True)
        self.assertEqual(result['error'],'REMOTE_REPO_DIRTY')
        self.assertFalse((self.root/'calls.jsonl').exists())
        self.assertEqual((self.repo/'dirty.txt').read_text(),'보존할 변경')

    def test_push_auth_failure_stops_before_ssh_without_exposing_git_output(self):
        output=self.base/'push-failed'
        def fake(args,**kwargs):
            self.assertEqual(args[0],'git')
            if args[-2:]==['status','--porcelain']:return subprocess.CompletedProcess(args,0,'','')
            if args[-2:]==['--show-current']:raise AssertionError('unexpected')
            if '--show-current' in args:return subprocess.CompletedProcess(args,0,'develop\n','')
            if args[-3:]==['remote','get-url','origin']:return subprocess.CompletedProcess(args,0,'https://github.com/jobchoi/toyproject-HowToEasy.git\n','')
            return subprocess.CompletedProcess(args,128,'PRIVATE-GIT-OUTPUT','PRIVATE-GIT-ERROR')
        with patch.object(sys,'argv',['remote_server.py','--host','pi-alias','--push','--apply','--output',str(output)]),patch.object(remote.subprocess,'run',side_effect=fake):
            self.assertEqual(remote.main(),2)
        report=(output/'report.md').read_text()
        self.assertIn('PUSH_AUTH_OR_COMMAND_FAILED',report)
        self.assertNotIn('PRIVATE-GIT',report)
