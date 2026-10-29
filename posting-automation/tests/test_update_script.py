"""Exercise safe fast-forward and dirty-check behavior using local temporary Git repos."""
from pathlib import Path
import shutil,subprocess,tempfile,unittest

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/update_project.sh'


class UpdateScriptTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.origin=self.root/'origin.git';self.author=self.root/'author';self.checkout=self.root/'checkout'
        self.git('init','--bare',str(self.origin));self.git('init','-b','develop',str(self.author))
        project=self.author/'posting-automation';(project/'scripts').mkdir(parents=True)
        shutil.copyfile(SCRIPT,project/'scripts/update_project.sh')
        (project/'scripts/setup_project.sh').write_text('#!/usr/bin/env bash\nset -eu\nmkdir -p "$(dirname "$0")/../.local"\nprintf "%s\\n" "$@" > "$(dirname "$0")/../.local/setup-called"\n')
        (project/'.gitignore').write_text('.local/\n');(self.author/'version.txt').write_text('v1')
        self.commit();self.git('remote','add','origin',str(self.origin),cwd=self.author);self.git('push','-u','origin','develop',cwd=self.author)
        self.git('clone','-b','develop',str(self.origin),str(self.checkout))

    def git(self,*args,cwd=None):return subprocess.run(['git',*args],cwd=cwd,capture_output=True,text=True,check=True)
    def commit(self):
        self.git('add','.',cwd=self.author)
        self.git('-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','test',cwd=self.author)

    def test_fast_forward_then_setup(self):
        (self.author/'version.txt').write_text('v2');self.commit();self.git('push',cwd=self.author)
        result=subprocess.run(['bash',str(self.checkout/'posting-automation/scripts/update_project.sh'),'--profile','test'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual((self.checkout/'version.txt').read_text(),'v2')
        self.assertIn('test',(self.checkout/'posting-automation/.local/setup-called').read_text())

    def test_dirty_checkout_is_preserved(self):
        path=self.checkout/'version.txt';path.write_text('user work')
        result=subprocess.run(['bash',str(self.checkout/'posting-automation/scripts/update_project.sh')],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertEqual(path.read_text(),'user work')
        self.assertFalse((self.checkout/'posting-automation/.local/setup-called').exists())
