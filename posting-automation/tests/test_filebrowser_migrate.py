from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import filebrowser_migrate as migration
import manage_server as manager
from posting_deploy import save_json


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name).resolve(); self.root=self.path/'web-server'
        self.log=manager.Log(self.path/'logs');self.addCleanup(self.log.close)
        manager.apply(self.root,['filebrowser'],None,self.log)
        old=self.path/'old';old.mkdir();self.original=old/'compose.yaml';self.original.write_text('private settings')
        self.override=self.root/'filebrowser/health.override.json';self.override.write_text('{}')
        self.storage=old/'storage';self.storage.mkdir()
        records=manager.registry(self.root);records['projects']['filebrowser'].update(legacy_compose=str(self.original),legacy_compose_overrides=[str(self.override)])
        save_json(self.root/'projects.json',records)
        mounts=[{'Type':'bind','Source':str(self.storage),'Destination':'/srv','RW':True}]
        for dest,name in [('/config/settings.json','settings.json'),('/database/filebrowser.db','filebrowser.db')]:
            p=old/name;p.write_text('private data');mounts.append({'Type':'bind','Source':str(p),'Destination':dest,'RW':True})
        mounts += [{'Type':'volume','Source':'/docker/'+d,'Destination':'/'+d,'Name':'anonymous-'+d,'RW':True} for d in ('config','database')]
        self.info={'project':'my-server','service':'fileserver','health':'healthy','image':'sha256:'+'a'*64,'working_dir':str(old),'files':str(self.original)+','+str(self.override),'mounts':mounts}
        self.runtime=dict(self.info,id='old-id',running=True,networks={'my-server_default':{}})
        self.new=dict(self.runtime,id='new-id',project='filebrowser')
        self.model={'services':{'fileserver':{'image':'latest','networks':{'default':None},'healthcheck':{'test':['CMD','wget']},'volumes':[{'type':'bind','source':m['Source'],'target':m['Destination']} for m in mounts if m['Type']=='bind']},'nginx':{'image':'nginx'}}}
        self.calls=[]

    def fake(self,args,log,code,**kwargs):
        self.calls.append((args,code))
        if code=='SOURCE_CONFIG':return json.dumps(self.model)
        if code=='TARGET_CONFIG':return json.dumps({'services':{'fileserver':{}}})
        if code=='RECOVERY_LOOKUP':return ''
        return ''

    def contexts(self):
        return patch.object(migration,'inspect',return_value=self.info),patch.object(migration,'container',side_effect=lambda log,name:self.new if any(code=='TARGET_START' for _,code in self.calls) else self.runtime),patch.object(migration,'run',side_effect=self.fake),patch.object(migration,'copy_archive',return_value='verified-hash')

    def test_plan_preserves_files_and_no_mutation(self):
        a,b,c,d=self.contexts()
        with a,b,c,d:migration.operate(self.root,False,self.log)
        self.assertEqual([code for _,code in self.calls],['SOURCE_CONFIG'])
        self.assertFalse((self.root/'filebrowser/compose.yaml').exists())

    def test_switch_keeps_mounts_and_old_container(self):
        a,b,c,d=self.contexts()
        with a,b,c,d:migration.operate(self.root,True,self.log)
        state=json.loads((self.root/'filebrowser/migration.json').read_text())
        self.assertEqual(state['state'],'switched_pending_review')
        codes=[c for _,c in self.calls];self.assertIn('SOURCE_PRESERVE',codes)
        self.assertFalse(any('rm' in args or 'down' in args or 'prune' in args for args,_ in self.calls))
        candidate=json.loads((self.root/'filebrowser/compose.yaml').read_text())
        self.assertEqual(set(candidate['services']),{'fileserver'})
        self.assertTrue(all(v['external'] for v in candidate['volumes'].values()))
        self.assertEqual(candidate['networks']['default']['name'],'my-server_default')
        self.assertTrue(self.original.exists())
        self.assertNotIn('private data',self.log.path.read_text())

    def test_failed_start_before_new_container_restores_old(self):
        base=self.fake
        def fail(args,log,code,**kwargs):
            if code=='TARGET_START':raise ValueError('failed start')
            return base(args,log,code,**kwargs)
        a,b,c,d=self.contexts()
        with a,b,patch.object(migration,'run',side_effect=fail),d:
            with self.assertRaises(ValueError):migration.operate(self.root,True,self.log)
        codes=[c for _,c in self.calls]
        self.assertIn('RECOVERY_RENAME',codes);self.assertIn('RECOVERY_START',codes)
        self.assertEqual(json.loads((self.root/'filebrowser/migration.json').read_text())['state'],'rolled_back')

    def test_dependency_rejected_before_stop(self):
        self.model['services']['fileserver']['depends_on']={'database':{}}
        a,b,c,d=self.contexts()
        with a,b,c,d:
            with self.assertRaisesRegex(ValueError,'DEPENDENCY'):migration.operate(self.root,True,self.log)
        self.assertNotIn('SOURCE_STOP',[code for _,code in self.calls])

    def test_archive_actual_restore_and_link_rejection(self):
        archive=self.path/'backup.tar'
        with tarfile.open(archive,'w') as tar:
            entry=tarfile.TarInfo('config/settings.json');entry.size=4;entry.mode=0o600;tar.addfile(entry,io.BytesIO(b'data'))
        self.assertEqual(len(migration.verify_archive(archive)),64)
        bad=self.path/'link.tar'
        with tarfile.open(bad,'w') as tar:
            entry=tarfile.TarInfo('../escape');entry.size=1;tar.addfile(entry,io.BytesIO(b'x'))
        with self.assertRaisesRegex(ValueError,'BACKUP_TYPE'):migration.verify_archive(bad)

    def test_rollback_only_expected_new_container(self):
        a,b,c,d=self.contexts()
        with a,b,c,d:migration.operate(self.root,True,self.log)
        self.calls.clear()
        with patch.object(migration,'container',return_value=self.new),patch.object(migration,'run',side_effect=self.fake):migration.operate(self.root,True,self.log,rollback=True)
        self.assertEqual([code for _,code in self.calls],['NEW_STOP','NEW_REMOVE','OLD_RENAME','OLD_START'])
        self.assertFalse(any('-v' in args for args,_ in self.calls))
