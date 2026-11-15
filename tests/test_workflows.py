import json
import os
from pathlib import Path
from datetime import datetime,timezone
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch,MagicMock
from zoneinfo import ZoneInfo
import store,connectors,monitoring,network
from research import research
from diagnostics import failure
from fastapi.testclient import TestClient
from app import app

class WorkflowTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.old=store.DATA;store.DATA=Path(self.temp.name);store.init(seed_demo=False)
  self.env=patch.dict(os.environ,{'FINN_AI_PROVIDER':'openai','GEMINI_API_KEY':'','OPENAI_API_KEY':'','FINN_DISABLE_MONITOR':'1'});self.env.start()
  with store.db() as c:
   c.execute("INSERT INTO companies VALUES ('TCS','Tata Consultancy Services','IT Services',1)")
 def tearDown(self):
  self.env.stop();store.DATA=self.old;self.temp.cleanup()
 def pdf(self,symbol,kind,text,period='FY2026'):
  with patch.object(store,'PdfReader',return_value=SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda:text)])):
   return store.import_pdf(b'%PDF-1.4 '+text.encode(),symbol,symbol+' '+period,kind,period)
 def test_migration_preserves_saved_documents_contacts_settings(self):
  doc=self.pdf('TCS','annual_report','Business segment revenue is described for the reporting year. '*5)
  with store.db() as c:
   c.execute("INSERT INTO events VALUES ('saved','TCS','Results','Results','2026-01-01T00:00:00+00:00',90,'',?,'',1,1,1)",(doc,))
   c.execute("UPDATE settings SET value='7.5' WHERE key='price_threshold'")
   c.execute("INSERT INTO contacts VALUES ('x','{}')")
  store.init(seed_demo=False);store.init(seed_demo=False)
  self.assertEqual(store.settings()['price_threshold'],7.5)
  self.assertEqual(store.rows('SELECT saved,read FROM events')[0],{'saved':1,'read':1})
  self.assertEqual(len(store.rows('SELECT * FROM documents')),1)
  self.assertEqual(len(store.rows('SELECT * FROM schema_migrations')),3)
  self.assertEqual(len(store.rows('SELECT * FROM contacts')),1)
 def test_document_diversity_period_selection_and_no_cross_company(self):
  annual=self.pdf('TCS','annual_report','Business revenue margin cash flow driver growth. '*600,'FY2026')
  call=self.pdf('TCS','transcript','Management revenue demand outlook margin utilisation commentary. '*15,'Q1 FY2027')
  self.pdf('OTHER','transcript','Business revenue margin cash flow wrong company. '*100,'Q1 FY2027')
  retrieved=store.retrieve('TCS','business growth and management margins')
  self.assertEqual({r['document_id'] for r in retrieved},{annual,call})
  only=store.retrieve('TCS','revenue',periods=['Q1 FY2027'])
  self.assertEqual({r['document_id'] for r in only},{call})
  self.assertEqual(store.retrieve('TCS','revenue',periods=['Q4 FY2099']),[])
  self.assertTrue(store.coverage('TCS')['gaps'])
 def test_discovery_labels_are_not_reporting_periods(self):
  html='''<h1>Example Limited</h1><div><h3>Annual reports</h3><ul><li><a href="https://example.org/a.pdf">Annual Report 2026</a></li></ul></div><div><h3>Concalls</h3><ul><li>Jul 2026 <a href="https://example.org/q1-2025.pdf">Transcript</a><a href="https://example.org/news">PPT</a></li></ul></div>'''
  found=connectors.parse_discovery(html,'https://www.screener.in/company/EXAMPLE/','EXAMPLE')
  self.assertEqual(len(found),2);self.assertEqual(found[1]['period'],'')
  self.assertIn('Jul 2026',found[1]['discovery_label'])
  self.assertEqual(found[1]['discovery_url'],'https://www.screener.in/company/EXAMPLE/')
 def test_filings_idempotent_and_publication_time_preserved(self):
  data=[{'symbol':'TCS','desc':'Financial results','an_dt':'11-Nov-2026 10:30:00','attchmntFile':'https://example.org/report.pdf'},
        {'symbol':'OTHER','desc':'Results','an_dt':'11-Nov-2026 10:30:00'},
        {'symbol':'TCS','desc':'Missing date'}]
  added,ids=connectors.ingest_filings(data,{'TCS'});self.assertEqual(added,1)
  self.assertEqual(connectors.ingest_filings(data,{'TCS'})[0],0)
  self.assertEqual(store.rows('SELECT published FROM events')[0]['published'],'2026-11-11T10:30:00+05:30')
  self.assertEqual(monitoring.create_alerts('filings',{'event_ids':ids}),1)
  self.assertEqual(monitoring.create_alerts('filings',{'event_ids':ids}),0)
 def test_price_alert_is_one_per_session_and_ignores_split(self):
  config=store.settings();data=connectors.evaluate_prices([100]*21+[106],[100]*21+[300],['2026-11-10']*22,config)
  with store.db() as c:c.execute('INSERT INTO prices VALUES (?,?)',('TCS',json.dumps(data)))
  self.assertEqual(monitoring.create_alerts('prices',{'updated_tickers':['TCS']}),1)
  self.assertEqual(monitoring.create_alerts('prices',{'updated_tickers':['TCS']}),0)
  data['date']='2026-11-11';data['corporate_action']=True
  with store.db() as c:c.execute('UPDATE prices SET data=?',(json.dumps(data),))
  self.assertEqual(monitoring.create_alerts('prices',{'updated_tickers':['TCS']}),0)
 def test_completed_sessions_and_scheduler_ist(self):
  local=datetime(2026,11,11,15,59,tzinfo=ZoneInfo('Asia/Kolkata'))
  self.assertFalse(connectors.completed_session(local,local))
  self.assertTrue(connectors.completed_session(local,local.replace(hour=16)))
  self.assertFalse(connectors.completed_session(local.replace(day=12),local.replace(hour=16)))
  monitor=monitoring.Monitor()
  self.assertFalse(monitor.due('prices',local));self.assertTrue(monitor.due('prices',local.replace(hour=16)))
  self.assertFalse(monitor.due('prices',datetime(2026,11,14,17,tzinfo=local.tzinfo)))
 def test_failed_source_health_is_persisted_and_safe(self):
  with patch('connectors.refresh_filings',side_effect=ConnectionError('secret-key-url')):
   with self.assertRaises(ValueError):monitoring.run_refresh('filings')
  health=monitoring.source_health()['filings']
  self.assertEqual(health['status'],'failed');self.assertEqual(health['error_code'],'connectivity')
  self.assertNotIn('secret',health['error']);self.assertIsNone(health['last_success'])
 def test_refresh_overlap_is_rejected(self):
  monitoring._locks['filings'].acquire()
  try:self.assertTrue(monitoring.run_refresh('filings')['skipped'])
  finally:monitoring._locks['filings'].release()
 def test_network_multiple_employers_explicit_second_degree_and_validation(self):
  p={'id':'a','name':'Alex','role':'Advisor','company':'OTHER','sector':'IT Services','tags':['cash flow'],'education':'IIT','relationship':'Known colleague','degree':1,'links':['b'],'employment':[{'company':'TCS','role':'Finance','start':'2018-01-01','end':'2022-01-01'},{'company':'OTHER','role':'Advisor','start':'2022-01-01'}]}
  q={**p,'id':'b','name':'Blair','degree':2,'links':[]}
  network.import_contacts(network.ContactImport(contacts=[p,q],replace=True))
  found=network.contacts('TCS');self.assertEqual(len(found),2)
  self.assertEqual(found[1]['connection_path'],['You','Alex','Blair'])
  self.assertIn('Worked at TCS',found[0]['reason'])
  self.assertEqual(network.contacts('UNKNOWN'),[])
  with self.assertRaises(ValueError):network.import_contacts(network.ContactImport(contacts=[{**p,'links':['missing']}]))
  self.assertEqual(len(store.rows('SELECT * FROM contacts')),2)
  with self.assertRaises(ValueError):network.ContactImport(contacts=[{**p,'employment':[{'company':'TCS','role':'Analyst','start':'2024-01-01','end':'2020-01-01'}]}])
 def test_reviewer_receives_only_each_claims_cited_passage(self):
  self.pdf('TCS','annual_report','Revenue grew ten percent; operating cash flow was positive. '*10)
  self.pdf('TCS','transcript','Management expects demand uncertainty to continue. '*10,'Q1 FY2027')
  citations=store.retrieve('TCS','Revenue demand');cid='S'+str(citations[0]['id'])
  client=MagicMock();client.responses.create.side_effect=[SimpleNamespace(output_text=json.dumps({'findings':[{'text':'Supported claim','sources':[cid]}],'limitations':[]})),SimpleNamespace(output_text=json.dumps({'checks':[{'index':0,'supported':True,'supports':[{'source':cid,'quote':'Revenue grew ten percent; operating cash flow was positive.'}]}]}))]
  with patch.dict(os.environ,{'FINN_AI_PROVIDER':'openai','GEMINI_API_KEY':'','OPENAI_API_KEY':'not-real'}),patch('openai.OpenAI',return_value=client):r=research('TCS','Revenue demand')
  for call in client.responses.create.call_args_list:
   self.assertIn('JSON',call.kwargs['input'])
  payload=json.loads(client.responses.create.call_args.kwargs['input'])
  self.assertEqual([s['id'] for s in payload['claims'][0]['evidence']],[cid])
  self.assertEqual(r['mode'],'ai');self.assertTrue(r['diagnostics']['reviewer_completed'])
 def test_malformed_review_fails_closed_and_errors_are_classified(self):
  self.pdf('TCS','annual_report','Revenue grew ten percent; operating cash flow was positive. '*10)
  cid='S'+str(store.retrieve('TCS','Revenue')[0]['id'])
  client=MagicMock();client.responses.create.side_effect=[SimpleNamespace(output_text=json.dumps({'findings':[{'text':'Claim','sources':[cid]}]})),SimpleNamespace(output_text='{"approved":[true],"issues":[]}')]
  with patch.dict(os.environ,{'FINN_AI_PROVIDER':'openai','GEMINI_API_KEY':'','OPENAI_API_KEY':'not-real'}),patch('openai.OpenAI',return_value=client):r=research('TCS','Revenue')
  self.assertEqual(r['mode'],'evidence');self.assertEqual(r['diagnostics']['fallback_code'],'validation')
  class Quota(Exception):status_code=429;body={'code':'insufficient_quota'}
  self.assertEqual(failure(Quota())['code'],'quota')
  self.assertEqual(failure(TimeoutError())['code'],'timeout')
 def test_event_document_link_and_read_state_api(self):
  with store.db() as c:c.execute("INSERT INTO events VALUES ('live','TCS','Results','Results','2026-11-11T00:00:00+00:00',90,'',NULL,'https://example.org/a.pdf',0,0,0)")
  doc=self.pdf('TCS','filing','Results show cash flow and profit in the reporting period. '*10)
  client=TestClient(app)
  with patch('connectors.download',return_value=(b'%PDF-test','https://example.org/a.pdf')),patch('store.import_pdf',return_value=doc):
   r=client.post('/api/documents/import',json={'ticker':'OTHER','url':'https://example.org/a.pdf','title':'Test','kind':'filing','event_id':'live','identity_confirmed':True})
   self.assertEqual(r.status_code,400)
  monitoring.create_alerts('filings',{'event_ids':['live']})
  alerts=client.get('/api/notifications').json();self.assertEqual(alerts['unread'],1)
  self.assertEqual(client.patch('/api/notifications/'+alerts['items'][0]['id'],json={'read':True}).status_code,200)
  self.assertEqual(client.get('/api/notifications').json()['unread'],0)
  self.assertEqual(client.post('/api/documents/import',json={'ticker':'TCS','url':'https://example.org/a.pdf','title':'Test','kind':'filing'}).status_code,400)
 def test_failed_refresh_does_not_alert_on_stale_prices(self):
  data=connectors.evaluate_prices([100]*21+[120],[100]*21+[400],['2020-01-01']*22,store.settings())
  with store.db() as c:c.execute('INSERT INTO prices VALUES (?,?)',('TCS',json.dumps(data)))
  with patch('connectors.refresh_prices',return_value={'updated':0,'updated_tickers':[],'failed':[{'ticker':'TCS','code':'connectivity'}]}):
   result=monitoring.run_refresh('prices')
  self.assertEqual(result['status'],'failed');self.assertEqual(result['alerts_created'],0)
  self.assertEqual(store.rows('SELECT * FROM alerts'),[])
 def test_symbol_migration_keeps_historical_evidence(self):
  doc=self.pdf('TATAMOTORS','filing','Historic results include revenue and business operations before the demerger. '*3)
  with store.db() as c:
   c.execute("UPDATE companies SET portfolio=1 WHERE ticker='TATAMOTORS'")
   c.execute('DELETE FROM schema_migrations WHERE version=2')
  store.init(seed_demo=False)
  self.assertEqual(store.rows("SELECT portfolio FROM companies WHERE ticker='TMPV'")[0]['portfolio'],1)
  self.assertEqual(store.rows("SELECT portfolio FROM companies WHERE ticker='TATAMOTORS'")[0]['portfolio'],0)
  self.assertEqual(store.rows('SELECT ticker FROM documents WHERE id=?',(doc,))[0]['ticker'],'TATAMOTORS')
 def test_contact_replacement_survives_startup_seed(self):
  import seed
  person={'id':'only','name':'Only Contact','role':'Operator','company':'TCS','relationship':'Known colleague','degree':1,'employment':[{'company':'TCS','role':'Operator','start':'2020-01-01'}]}
  network.import_contacts(network.ContactImport(contacts=[person],replace=True))
  with patch('seed.COMPANIES',[]),patch('seed.EVENTS',[]):seed.seed()
  self.assertEqual([p['id'] for p in store.rows('SELECT id FROM contacts')],['only'])
 def test_matching_event_pdf_import_links_document(self):
  import time
  with store.db() as c:c.execute("INSERT INTO events VALUES ('live','TCS','Results','Results','2026-11-11T00:00:00+00:00',90,'',NULL,'https://example.org/a.pdf',0,0,0)")
  doc=self.pdf('TCS','filing','Results show revenue, profit and cash flow for the reporting period. '*5)
  client=TestClient(app)
  with patch('connectors.download',return_value=(b'%PDF-test','https://example.org/a.pdf')),patch('store.import_pdf',return_value=doc):
   r=client.post('/api/documents/import',json={'ticker':'TCS','url':'https://example.org/a.pdf','title':'Test','kind':'filing','event_id':'live','identity_confirmed':True})
   self.assertEqual(r.status_code,200)
   for _ in range(100):
    job=client.get('/api/jobs/'+r.json()['job_id']).json()
    if job['status'] in ('completed','failed'):break
    time.sleep(.01)
   self.assertEqual(job['status'],'completed',job)
  self.assertEqual(client.get('/api/events/live').json()['document_id'],doc)
 def test_scheduler_tick_creates_alert_and_second_owner_cannot_start(self):
  data=[{'symbol':'TCS','desc':'Financial results','an_dt':'11-Nov-2026 10:30:00'}]
  _,ids=connectors.ingest_filings(data,{'TCS'})
  runner=monitoring.Monitor()
  runner.stop_event=MagicMock()
  runner.stop_event.wait.side_effect=[False,True]
  runner.stop_event.is_set.return_value=False
  with patch.object(runner,'due',side_effect=lambda kind,current:kind=='filings'),patch('connectors.refresh_filings',return_value={'added':1,'event_ids':ids}):runner.loop()
  self.assertEqual(len(store.rows('SELECT * FROM alerts')),1)
  first=monitoring.Monitor();second=monitoring.Monitor()
  try:
   with patch.dict(os.environ,{'FINN_DISABLE_MONITOR':'0'}):
    first.start();second.start()
    self.assertIsNotNone(first.thread);self.assertIsNone(second.thread)
  finally:first.stop();second.stop()
 def test_restart_marks_unfinished_refresh_interrupted(self):
  with store.db() as c:c.execute("INSERT INTO refresh_runs(id,source,started_at,status) VALUES ('old','filings',?,'running')",(store.now(),))
  with patch('app.seed.seed'):
   with TestClient(app) as client:
    health=client.get('/api/health').json()['sources']['filings']
    self.assertEqual(health['status'],'interrupted');self.assertEqual(health['error_code'],'restart')
