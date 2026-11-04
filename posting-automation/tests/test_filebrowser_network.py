from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import filebrowser_network as network
import filebrowser_migrate as migration
import manage_server as manager
from posting_deploy import save_json


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()/'web-server';self.log=manager.Log(Path(self.tmp.name)/'logs');self.addCleanup(self.log.close)
        manager.apply(self.root,['filebrowser'],None,self.log)
        save_json(self.root/'filebrowser/migration.json',{'state':'switched_pending_review','new_id':'new','old_id':'old','old_name':'file-service-before-1234567890'})
        self.current={'id':'new','image':'same','running':True,'health':'healthy','project':'filebrowser','ports':{'80/tcp':[{'HostIp':'','HostPort':'8080'}]},'actual_ports':{},'networks':{},'network_mode':'my-server_default','mounts':[{'Type':'bind','Source':'/data/db','Destination':'/database/filebrowser.db','RW':True}]}
        self.old=dict(self.current,id='old',project='my-server',running=False,restart={'Name':'no'})
        self.calls=[];self.joined=False

    def ready(self):
        return dict(self.current,networks={'my-server_default':{'EndpointID':'attached'}},actual_ports={'80/tcp':[{'HostIp':'0.0.0.0','HostPort':'8080'}]})

    def inspect(self,log,name):
        if name!='file-service':return self.old
        return self.ready() if self.joined else self.current

    def fake_run(self,args,log,code,**kwargs):
        self.calls.append((args,code))
        if code=='ENDPOINT_CONNECT':self.joined=True
        return json.dumps({'name':'my-server_default','driver':'bridge','internal':False}) if code=='ENDPOINT_NETWORK' else ''

    def test_plan_then_connect_preserves_container_and_data(self):
        with patch.object(network,'container',side_effect=self.inspect),patch.object(network,'run',side_effect=self.fake_run),patch.object(network,'local_health',return_value=True):
            network.repair(self.root,False,self.log)
            self.assertFalse(self.joined)
            network.repair(self.root,True,self.log)
        self.assertEqual(sum(code=='ENDPOINT_CONNECT' for _,code in self.calls),1)
        self.assertFalse(any('rm' in args or 'restart' in args or 'up' in args for args,_ in self.calls))
        state=json.loads((self.root/'filebrowser/migration.json').read_text());self.assertEqual(state['endpoint_state'],'verified')

    def test_internal_health_without_endpoint_is_not_reachable(self):
        self.assertFalse(network.endpoint_ready(self.current))
        self.assertTrue(network.endpoint_ready(self.ready()))
        with patch.object(migration,'container',side_effect=self.inspect),patch('filebrowser_network.local_health',return_value=True):
            with self.assertRaisesRegex(ValueError,'STABILIZE_ENDPOINT'):migration.stabilize(self.root,False,self.log)

    def test_data_drift_prevents_network_change(self):
        self.old=deepcopy(self.old);self.old['mounts'][0]['Source']='/different/db'
        with patch.object(network,'container',side_effect=self.inspect),patch.object(network,'run',side_effect=self.fake_run):
            with self.assertRaisesRegex(ValueError,'ENDPOINT_DATA'):network.repair(self.root,True,self.log)
        self.assertFalse(self.calls)

    def test_http_failure_never_marks_success_or_reconnects(self):
        with patch.object(network,'container',side_effect=self.inspect),patch.object(network,'run',side_effect=self.fake_run),patch.object(network,'local_health',return_value=False),patch.object(network.time,'monotonic',side_effect=[0,100]):
            with self.assertRaisesRegex(ValueError,'ENDPOINT_VERIFY'):network.repair(self.root,True,self.log)
        self.assertEqual(sum(code=='ENDPOINT_CONNECT' for _,code in self.calls),1)
        self.assertEqual(json.loads((self.root/'filebrowser/migration.json').read_text())['endpoint_state'],'check_required')

    def test_already_connected_does_not_change_anything(self):
        self.joined=True
        with patch.object(network,'container',side_effect=self.inspect),patch.object(network,'run',side_effect=self.fake_run),patch.object(network,'local_health',return_value=True):network.repair(self.root,True,self.log)
        self.assertFalse(self.calls)
