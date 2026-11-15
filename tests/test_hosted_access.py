import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
import access,store
from app import app

class HostedAccessTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.old=store.DATA;store.DATA=Path(self.temp.name);store.init(seed_demo=False)
  self.env=patch.dict(os.environ,{'FINN_REQUIRE_ACCESS':'1','FINN_ACCESS_USER':'finn','FINN_ACCESS_PASSWORD':'offline-test-password-only','FINN_DISABLE_MONITOR':'1','OPENAI_API_KEY':''});self.env.start()
  self.client=TestClient(app)
 def tearDown(self):self.env.stop();store.DATA=self.old;self.temp.cleanup()
 def test_anonymous_users_cannot_read_or_write_workspace(self):
  for url in ('/','/docs','/openapi.json','/static/app.js','/api/overview','/api/health','/api/documents/missing/file'):
   with self.subTest(url=url):
    r=self.client.get(url);self.assertEqual(r.status_code,401);self.assertIn('Basic',r.headers['www-authenticate'])
    self.assertNotIn('offline-test-password-only',r.text)
  self.assertEqual(self.client.put('/api/settings',json={}).status_code,401)
  self.assertFalse(store.rows('SELECT * FROM jobs'))
 def test_readiness_is_minimal_and_available_without_credentials(self):
  self.assertEqual(self.client.get('/healthz').json(),{'status':'ok'})
  self.assertEqual(self.client.head('/healthz').status_code,200)
  self.assertEqual(self.client.post('/healthz').status_code,401)
  with patch('app.db',side_effect=OSError('private filesystem details')):
   r=self.client.get('/healthz');self.assertEqual(r.status_code,503);self.assertNotIn('private',r.text)
 def test_correct_authentication_and_bad_credentials(self):
  self.assertEqual(self.client.get('/api/overview',auth=('finn','offline-test-password-only')).status_code,200)
  self.assertEqual(self.client.get('/api/overview',auth=('other','offline-test-password-only')).status_code,401)
  self.assertEqual(self.client.get('/api/overview',auth=('finn','wrong')).status_code,401)
  for value in ('Basic !!!!','Bearer wrong','Basic YQ=='):
   self.assertEqual(self.client.get('/api/overview',headers={'Authorization':value}).status_code,401)
 def test_host_requires_a_password_and_local_mode_is_optional(self):
  for password in ('','short'):
   with patch.dict(os.environ,{'FINN_ACCESS_PASSWORD':password}):
    with self.assertRaises(ValueError):access.validate_configuration()
  with patch.dict(os.environ,{'FINN_REQUIRE_ACCESS':'0','FINN_ACCESS_PASSWORD':''}):
   access.validate_configuration();self.assertEqual(self.client.get('/api/overview').status_code,200)
 def test_proxy_https_origin_allows_authenticated_same_origin_writes(self):
  client=TestClient(ProxyHeadersMiddleware(app,trusted_hosts='*'),base_url='http://finn.example')
  headers={'X-Forwarded-Proto':'https','Origin':'https://finn.example'}
  result=client.put('/api/settings',headers=headers,auth=('finn','offline-test-password-only'),json=store.settings())
  self.assertEqual(result.status_code,200)
  self.assertEqual(client.put('/api/settings',headers={**headers,'Origin':'https://foreign.example'},auth=('finn','offline-test-password-only'),json=store.settings()).status_code,403)
 def test_free_hosting_state_reset_notice_is_explicit_and_environment_scoped(self):
  with patch.dict(os.environ,{'FINN_EPHEMERAL_DEMO':'1'}):
   notice=self.client.get('/api/overview',auth=('finn','offline-test-password-only')).json()['hosting_notice']
   self.assertIn('reset',notice);self.assertIn('Bundled public documents restore automatically',notice)
   self.assertIn('Monitoring pauses',notice)
  with patch.dict(os.environ,{'FINN_EPHEMERAL_DEMO':'0'}):
   self.assertIsNone(self.client.get('/api/overview',auth=('finn','offline-test-password-only')).json()['hosting_notice'])
