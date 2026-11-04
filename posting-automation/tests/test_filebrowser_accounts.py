from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from filebrowser_accounts import usernames


class AccountOutputTests(unittest.TestCase):
    def test_only_usernames_are_returned(self):
        output='ID  Username  Scope  Password\n1   sample-admin  /  HASH_MUST_NOT_LEAK\n2   writer  /  ANOTHER_HASH\n'
        result=usernames(output)
        self.assertEqual(result,['sample-admin','writer'])
        self.assertNotIn('HASH',str(result))
    def test_unknown_output_is_not_guessed_as_admin(self):
        with self.assertRaises(ValueError):usernames('database locked')


class SnapshotTests(unittest.TestCase):
    def exercise(self,fail=False):
        import tempfile
        from unittest.mock import patch
        import filebrowser_accounts as accounts
        import manage_server as manager
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder).resolve();root=base/'web-server';(root/'filebrowser/backups').mkdir(parents=True)
            source=base/'original.db';source.write_bytes(b'ORIGINAL_DATABASE')
            log=manager.Log(base/'logs');calls=[]
            current={'id':'expected-id','project':'filebrowser','image':'sha256:'+'a'*64,'running':True,'mounts':[{'Type':'bind','Destination':'/database/filebrowser.db','Source':str(source)}]}
            def run(args,log,code,**kwargs):
                calls.append((args,code));return 'ID Username Password\n1 sample-user PRIVATE_HASH'
            try:
                with patch.object(accounts,'container',return_value=current),patch.object(accounts,'run',side_effect=run),patch.object(accounts,'local_health',return_value=True):
                    if fail:
                        with patch.object(accounts.shutil,'copyfile',side_effect=OSError('copy failed')):
                            with self.assertRaises(OSError):accounts.inspect_accounts(root,True,log)
                    else:self.assertEqual(accounts.inspect_accounts(root,True,log),['sample-user'])
                self.assertEqual(source.read_bytes(),b'ORIGINAL_DATABASE')
                self.assertIn('ACCOUNT_RESUME',[code for _,code in calls])
                self.assertNotIn('PRIVATE_HASH',log.path.read_text())
                if not fail:
                    args=next(args for args,code in calls if code=='ACCOUNT_QUERY')
                    self.assertIn('none',args);self.assertIn('--read-only',args)
                    self.assertNotIn(str(source),args)
            finally:log.close()
    def test_snapshot_query_preserves_original(self):self.exercise()
    def test_copy_failure_always_resumes_service(self):self.exercise(True)
