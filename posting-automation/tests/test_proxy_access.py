from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from posting_tool.web import create_app, configured_hosts

HOST = 'posting.example.ts.net'

class ProxyAccessTests(unittest.TestCase):
    def test_private_proxy_host_origin_and_forwarded_protocol(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', {'POSTING_ALLOWED_HOSTS':HOST}):
            app = ProxyHeadersMiddleware(create_app(Path(folder)), trusted_hosts=['127.0.0.1'])
            with TestClient(app, base_url='http://'+HOST+':8443', client=('127.0.0.1',12345)) as client:
                token = client.get('/api/config').json()['token']
                headers = {'X-Workspace-Token':token,'Origin':'https://'+HOST+':8443','X-Forwarded-Proto':'https'}
                result = client.post('/api/previews', json={'text':'프록시 경유 원고'}, headers=headers)
                self.assertEqual(result.status_code,200)
                self.assertEqual(client.get('/',headers={'Host':'other.example'}).status_code,400)
                self.assertEqual(client.post('/api/previews',json={'text':'원고'},headers={**headers,'Origin':'https://other.example'}).status_code,403)
                self.assertEqual(client.post('/api/previews',json={'text':'원고'},headers={**headers,'X-Workspace-Token':''}).status_code,403)
                self.assertEqual(client.post('/api/previews',json={'text':'원고'},headers={**headers,'X-Forwarded-Proto':'http'}).status_code,403)
            with TestClient(app,base_url='http://'+HOST+':8443',client=('192.0.2.1',12345)) as external:
                self.assertEqual(external.post('/api/previews',json={'text':'원고'},headers=headers).status_code,403)

    def test_default_is_local_and_wildcards_are_rejected(self):
        with patch.dict('os.environ',{'POSTING_ALLOWED_HOSTS':''}):
            self.assertNotIn(HOST,configured_hosts())
        for value in ('*','*.example.com','https://example.com','example.com:8443','foo/bar'):
            with patch.dict('os.environ',{'POSTING_ALLOWED_HOSTS':value}):
                with self.assertRaises(ValueError): configured_hosts()
