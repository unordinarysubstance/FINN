import os
import unittest
from unittest.mock import patch
from diagnostics import failure,quota_scope

class DiagnosticsTests(unittest.TestCase):
 def test_bad_request_exposes_safe_actionable_details(self):
  class ProviderError(Exception):
   status_code=400
   body={'error':{'code':'unsupported_parameter','param':'text.format','message':'Unsupported format for model. Key sk-secret123 and https://example.org/private?token=private-token'}}
  with patch.dict(os.environ,{'OPENAI_API_KEY':'sk-secret123','PRIVATE_TOKEN':'private-token'}):report=failure(ProviderError())
  self.assertEqual(report['code'],'invalid_request');self.assertEqual(report['http_status'],400)
  self.assertEqual(report['provider_param'],'text.format')
  self.assertNotIn('sk-secret123',str(report));self.assertNotIn('private-token',str(report));self.assertNotIn('https://',str(report))
  self.assertIn('Unsupported format',report['provider_message'])
 def test_unknown_exception_does_not_expose_its_message(self):
  r=failure(AttributeError('sensitive request contents'))
  self.assertEqual(r['exception_type'],'AttributeError');self.assertNotIn('sensitive',str(r))
 def test_known_document_validation_is_actionable(self):
  r=failure(ValueError('Company identity requires manual inspection.'))
  self.assertEqual(r['message'],'Company identity requires manual inspection.')
 def test_daily_limit_is_distinct_from_minute_limit(self):
  class ProviderError(Exception):status_code=429
  error=ProviderError()
  error.body={'error':{'message':'Please check billing details. limit: 20, Generate content requests per day limit exceeded on Free Tier.'}}
  daily=failure(error)
  self.assertEqual(daily['code'],'daily_quota');self.assertEqual(daily['quota_scope'],'daily')
  self.assertIn('daily reset',daily['message'])
  error.body={'error':{'message':'requests per minute limit exceeded'}}
  self.assertEqual(failure(error)['code'],'rate_limit');self.assertEqual(failure(error)['quota_scope'],'minute')
 def test_mixed_structured_daily_and_minute_limits_prefer_daily(self):
  body={'error':{'details':[{'@type':'type.googleapis.com/google.rpc.QuotaFailure','violations':[{'quotaId':'GenerateRequestsPerMinute'},{'quotaId':'GenerateRequestsPerDay'}]}]}}
  self.assertEqual(quota_scope(body),'daily')
  self.assertEqual(quota_scope({'error':{'message':'Quota exhausted'}}),'unknown')
