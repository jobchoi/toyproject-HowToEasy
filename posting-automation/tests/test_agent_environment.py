import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import agent_environment as doctor


class AgentEnvironmentTests(unittest.TestCase):
    def test_default_never_calls_ssh_and_never_emits_secret_values(self):
        calls=[]
        def command(args,timeout=10):
            calls.append(args)
            return 'ok','develop' if 'branch' in args else ''
        with patch.object(doctor,'check_command',side_effect=command),patch.dict(os.environ,{'GIT_ASKPASS':'SECRET_ASKPASS_PATH','SSH_AUTH_SOCK':'SECRET_SOCKET_PATH'}):
            data=doctor.inspect_environment()
        self.assertFalse(any(args[0]=='ssh' for args in calls))
        self.assertNotIn('SECRET_',str(data))

    def test_timeout_is_not_success_and_host_options_rejected(self):
        def command(args,timeout=10):return ('timeout','') if args[0]=='ssh' else ('ok','')
        with patch.object(doctor,'check_command',side_effect=command):
            data=doctor.inspect_environment(True)
        self.assertTrue(data['needs_attention'])
        self.assertEqual(next(r for r in data['checks'] if r['check']=='remote_ssh')['state'],'timeout')
        with self.assertRaises(ValueError):doctor.inspect_environment(True,'-oBad=1')
