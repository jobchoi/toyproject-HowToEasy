import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import filebrowser_inventory as module


class InventoryTests(unittest.TestCase):
    def test_overlap_uses_path_boundaries(self):
        self.assertTrue(module.overlap('/data/share', '/data/share/photos'))
        self.assertFalse(module.overlap('/data/share', '/data/shared'))

    def test_only_metadata_and_shared_mounts(self):
        base = {'image':'sha256:abc','state':'running','project':'my-server','service':'files',
                'files':'/old/compose.yaml','working_dir':'/old','ports':{},
                'networks':{'default':{'IPAddress':'PRIVATE_NETWORK_FIELD'}},
                'mounts':[{'Type':'bind','Source':'/old/storage','Destination':'/srv','RW':True,'Propagation':'PRIVATE_FIELD'}]}
        target = dict(base, name='/file-service')
        peer = dict(base, name='/web-service', service='web')
        def fake(args):
            if 'ps' in args: return 'one\ntwo\n'
            return json.dumps(target if args[-1]=='one' else peer)
        with patch.object(module, 'command', side_effect=fake), patch.object(module.os, 'walk', return_value=[]):
            result=module.inventory()
        self.assertEqual(result['shared_mounts'][0]['other_container'], 'web-service')
        text=json.dumps(result)
        self.assertNotIn('PRIVATE', text)
        self.assertEqual(result['target']['networks'], ['default'])
