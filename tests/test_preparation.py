import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import store
import manage

class PreparationTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  self.old=store.DATA;store.DATA=self.root/'runtime';store.init(seed_demo=False)
  self.item=dict(ticker='TEST',company_name='Test Limited',kind='transcript',title='Test Q1 FY2026',period='Q1 FY2026',url='https://example.org/call.pdf',discovery_url='https://example.org/ir',identity_status='content_verified')
  self.manifest=self.root/'manifest.json';self.manifest.write_text(json.dumps({'documents':[self.item]}))
 def tearDown(self):
  store.DATA=self.old;self.temp.cleanup()
 def test_offline_import_preserves_provenance_and_never_fetches(self):
  (self.root/manage.local_filename(self.item)).write_bytes(b'%PDF-fixture')
  with patch('manage.connectors.download') as fetch,patch('manage.validate_identity'),patch('manage.store.import_pdf',return_value='doc') as ingest:
   r=manage.prepare(self.manifest,local_dir=self.root)
  fetch.assert_not_called();self.assertEqual(r['documents'][0]['status'],'indexed')
  self.assertEqual(ingest.call_args.args[5],self.item['url'])
  self.assertEqual(ingest.call_args.kwargs['verification'],'local_manifest_and_content_checks')
 def test_missing_or_unverified_inbox_file_is_not_imported(self):
  with patch('manage.connectors.download') as fetch:
   r=manage.prepare(self.manifest,local_dir=self.root)
  self.assertEqual(r['documents'][0]['status'],'missing_local_file');fetch.assert_not_called()
  self.item['identity_status']='discovered_not_verified';self.item['period']=''
  self.manifest.write_text(json.dumps({'documents':[self.item]}))
  with patch('manage.store.import_pdf') as ingest:r=manage.prepare(self.manifest,local_dir=self.root)
  self.assertEqual(r['documents'][0]['status'],'manual_review_required');ingest.assert_not_called()
 def test_local_file_validation_failure_does_not_promote_coverage(self):
  (self.root/manage.local_filename(self.item)).write_bytes(b'%PDF-wrong-company')
  with patch('manage.validate_identity',side_effect=ValueError('Wrong company')),patch('manage.store.import_pdf') as ingest:
   r=manage.prepare(self.manifest,local_dir=self.root)
  ingest.assert_not_called();self.assertEqual(r['documents'][0]['status'],'failed')
  self.assertEqual(r['coverage'][0]['transcripts'],0)
 def test_live_verifier_stops_before_model_calls_when_dns_is_denied(self):
  import socket
  with patch('manage.socket.getaddrinfo',side_effect=socket.gaierror('Unavailable')),patch('manage.prepare') as acquire,patch('manage.research') as model:
   report=manage.verify(self.manifest,False,['TEST'])
  self.assertEqual(report['status'],'blocked');acquire.assert_not_called();model.assert_not_called()
  self.assertFalse(report['manual_review_complete'])
 def test_verifier_skips_batch_evaluation_after_failed_smoke(self):
  with patch('manage.socket.getaddrinfo',return_value=[object()]),patch('manage.prepare',return_value={'documents':[]}),patch('manage.store.rows',return_value=[]),patch('manage.research',return_value={'mode':'evidence'}),patch('manage.monitoring.run_refresh',return_value={'status':'completed'}),patch('manage.evaluate') as batch:
   r=manage.verify(self.manifest,False,['TEST'])
  batch.assert_not_called();self.assertEqual(r['evaluation']['status'],'skipped');self.assertEqual(r['status'],'incomplete')
 def test_targeted_evaluation_makes_one_research_request(self):
  answer={'mode':'ai','findings':[{'sources':['S1']}],'citations':[{'id':'S1'}],'diagnostics':{'reviewer_completed':True}}
  with patch('manage.research',return_value=answer) as model:
   r=manage.evaluate(['TEST'],[3])
  model.assert_called_once_with('TEST',manage.QUESTIONS[2])
  self.assertEqual(r['required'],1);self.assertEqual(r['passed_automated'],1)
  self.assertEqual(r['selection']['question_indexes'],[3])
 def test_check_ai_cli_writes_diagnostic_report_without_research(self):
  report={'status':'failed','provider':'gemini','probes':[]}
  with patch('sys.argv',['manage.py','check-ai']),patch('manage.store.init'),patch('manage.seed.seed'),patch('manage.check_ai',return_value=report),patch('manage.research') as research,patch('builtins.print'):
   status=manage.main()
  self.assertEqual(status,1);research.assert_not_called()
  self.assertEqual(json.loads((store.DATA/'verification'/'check-ai.json').read_text()),report)
 def test_evaluation_progress_reports_each_completed_answer(self):
  from unittest.mock import Mock
  progress=Mock()
  answer={'mode':'ai','findings':[{'sources':['S1']}],'citations':[{'id':'S1'}],'diagnostics':{'reviewer_completed':True}}
  with patch('manage.research',return_value=answer):result=manage.evaluate(['TEST'],[2],progress=progress)
  progress.assert_called_once_with('TEST',2,result['answers'][0],1,1)
