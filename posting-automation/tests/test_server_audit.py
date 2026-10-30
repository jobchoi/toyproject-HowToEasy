import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('server_audit',Path(__file__).resolve().parents[1]/'scripts/audit_server.py')
audit = importlib.util.module_from_spec(spec); spec.loader.exec_module(audit)

class ServerAuditTests(unittest.TestCase):
    def test_scan_skips_secrets_symlinks_and_preserves_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            project = root/'apps'/'project'; project.mkdir(parents=True)
            (project/'compose.yaml').write_text('SECRET-COMPOSE-CONTENT')
            (project/'compose.duct-tape.yml').write_text('PRIVATE-COMPOSE')
            (project/'.env').write_text('PASSWORD=DO-NOT-COLLECT')
            (project/'.git').mkdir()
            (project/'node_modules').mkdir(); (project/'node_modules'/'hidden').mkdir()
            (root/'link').symlink_to(project,target_is_directory=True)
            (root/'.ssh').mkdir(); (root/'.ssh'/'private').mkdir()
            with patch.object(audit,'git_info',return_value={'path':str(project),'branch':'my-server'}):
                report = audit.scan([root],4,100)
            encoded = json.dumps(report)
            self.assertIn('compose.yaml',encoded); self.assertIn('compose.duct-tape.yml',encoded); self.assertIn('my-server',encoded)
            for secret in ('SECRET-COMPOSE-CONTENT','PRIVATE-COMPOSE','DO-NOT-COLLECT','node_modules','private','/link'):
                self.assertNotIn(secret,encoded)
            self.assertEqual((project/'.env').read_text(),'PASSWORD=DO-NOT-COLLECT')
            self.assertEqual(len(audit.scan([root],0,100)['directories']),1)
            self.assertEqual(len(audit.scan([root],4,1)['directories']),1)

    def test_docker_only_requests_allowlisted_fields(self):
        calls = []
        def fake(args):
            calls.append(args)
            if args[1]=='ps':
                return json.dumps({'ID':'abc','Names':'posting','Image':'app','Command':'secret command','Ports':'127.0.0.1:8010->8010/tcp'}),None
            return json.dumps({'mounts':[{'Type':'bind','Source':'/srv/data','Destination':'/app/.local','RW':True,'Extra':'omit'}],'project':'posting','restart':'unless-stopped','working_dir':'/apps/posting','config_files':'/apps/posting/compose.yaml'}),None
        with patch.object(audit,'command',side_effect=fake):
            report = audit.docker_inventory()
        encoded = json.dumps(report)
        self.assertNotIn('secret command',encoded); self.assertNotIn('Extra',encoded)
        self.assertIn('/srv/data',encoded)
        template = calls[1][3]
        self.assertNotIn('Config.Env',template); self.assertNotIn('Config.Cmd',template)
        with patch.object(audit,'command',return_value=(None,'permission_denied_or_command_failed')):
            self.assertIn('error',audit.docker_inventory())

    def test_tailscale_redacts_proxy_credentials_and_content(self):
        data = {'Web':{'server.ts.net:8443':{'Handlers':{'/':{'Proxy':'http://user:password@127.0.0.1:8010/?token=secret'},'/text':{'Text':'PRIVATE CONTENT'}}}},'AllowFunnel':{'server.ts.net:443':True},'TCP':{'8443':{'HTTPS':True}}}
        with patch.object(audit,'command',return_value=(json.dumps(data),None)):
            report = audit.tailscale()
        text = json.dumps(report)
        for secret in ('password','secret','PRIVATE CONTENT'): self.assertNotIn(secret,text)
        self.assertEqual(report['routes'][0]['proxy'],'http://127.0.0.1:8010')
        self.assertTrue(report['funnel']['server.ts.net:443'])

    def test_listener_maps_working_directory_without_command_arguments(self):
        output = 'LISTEN 0 128 127.0.0.1:8010 0.0.0.0:* users:(("python",pid=123,fd=7))'
        with patch.object(audit,'command',return_value=(output,None)),patch.object(audit.os,'readlink',side_effect=['/apps/posting','/apps/posting/.venv/bin/python']):
            result = audit.listeners()['tcp'][0]
        self.assertEqual(result['listen'],'127.0.0.1:8010')
        self.assertEqual(result['processes'][0]['cwd'],'/apps/posting')
        self.assertNotIn('cmdline',json.dumps(result))

    def test_commands_timeout_and_stderr_are_not_reported(self):
        import subprocess
        with patch.object(audit.shutil,'which',return_value='/usr/bin/tool'),patch.object(audit.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'secret stdout','secret stderr')):
            self.assertEqual(audit.command(['tool']),(None,'permission_denied_or_command_failed'))
        with patch.object(audit.shutil,'which',return_value='/usr/bin/tool'),patch.object(audit.subprocess,'run',side_effect=subprocess.TimeoutExpired('tool',12)):
            self.assertEqual(audit.command(['tool']),(None,'unavailable_or_timeout'))
