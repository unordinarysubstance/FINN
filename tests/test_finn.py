import os,tempfile,time,unittest,sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import store,seed
from research import research
from connectors import evaluate_prices,public_url,classify
from fastapi.testclient import TestClient
from app import app

class FinnTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();cls.old_data=store.DATA;store.DATA=Path(cls.temp.name)
  cls.env=patch.dict(os.environ,{'OPENAI_API_KEY':'','FINN_DISABLE_MONITOR':'1','FINN_DISABLE_DEMO_SEED':'1'});cls.env.start()
  cls.client=TestClient(app);cls.client.__enter__()
 @classmethod
 def tearDownClass(cls):
  cls.client.__exit__(None,None,None);cls.env.stop();store.DATA=cls.old_data;cls.temp.cleanup()
 def fake_pdf(self,symbol,kind,text):
  reader=SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda:text)])
  with patch.object(store,'PdfReader',return_value=reader):return store.import_pdf(b'%PDF-1.4 '+text.encode(),symbol,'Test source',kind,'FY2025')
 def test_seed_and_metrics(self):
  overview=self.client.get('/api/overview').json()
  self.assertEqual(len([c for c in overview['companies'] if c['portfolio']]),18)
  e=self.client.get('/api/events/archive-RELIANCE').json()
  self.assertEqual(len(e['metrics']),4);self.assertEqual(e['metrics'][0]['current'],273252)
  self.assertEqual(e['metrics'][3]['current'],30681);self.assertEqual(e['metrics'][0]['yoy'],5.98)
  self.assertTrue(all(p['synthetic'] for p in e['contacts']))
 def test_company_isolation_and_primary_scope(self):
  self.fake_pdf('TESTONE','annual_report','Revenue increased through domestic sales. Cash flow improved and debt decreased during FY2025. '*10)
  self.fake_pdf('TESTTWO','annual_report','Revenue collapsed with extraordinary unicorn losses and negative cash flow in FY2025. '*10)
  self.fake_pdf('TESTONE','filing','Revenue includes a forbidden quarterly-only data point. '*10)
  r=research('TESTONE','Explain revenue and cash flow');self.assertGreater(len(r['citations']),0)
  joined=' '.join(c['excerpt'] for c in r['citations'])
  self.assertNotIn('unicorn',joined);self.assertNotIn('forbidden',joined)
  self.assertTrue(all(c['page']==1 for c in r['citations']))
 def test_missing_evidence_abstains(self):
  r=research('UNKNOWNCO','What did management promise?')
  self.assertEqual(r['findings'],[]);self.assertEqual(r['citations'],[]);self.assertTrue(r['limitations'])
 def test_duplicate_import(self):
  text='Cash flow and revenue from the annual report. '*8
  first=self.fake_pdf('DEDUP','annual_report',text)
  before=store.rows('SELECT count(*) n FROM chunks WHERE document_id=?',(first,))[0]['n']
  second=self.fake_pdf('DEDUP','annual_report',text);self.assertEqual(first,second)
  self.assertEqual(before,store.rows('SELECT count(*) n FROM chunks WHERE document_id=?',(first,))[0]['n'])
 def test_archive_not_in_live_feed(self):
  self.assertEqual(self.client.get('/api/events?mode=live&days=1').json()['items'],[])
  self.assertEqual(len(self.client.get('/api/events?mode=archive&days=365').json()['items']),5)
  narrow=self.client.get('/api/events?mode=archive&days=1').json()
  self.assertEqual(len(narrow['items']),1);self.assertEqual(narrow['items'][0]['ticker'],'LICI')
 def test_save_and_settings_persist(self):
  self.assertEqual(self.client.patch('/api/events/archive-TCS',json={'saved':True}).status_code,200)
  result=self.client.get('/api/events?mode=archive&days=365&saved=true').json()
  self.assertEqual([r['ticker'] for r in result['items']],['TCS'])
  config={'price_threshold':3.5,'volume_threshold':2.5,'categories':['Results'],'monitoring_enabled':False}
  self.assertEqual(self.client.put('/api/settings',json=config).json(),config)
  self.assertEqual(self.client.get('/api/overview').json()['settings'],config)
  self.assertEqual(self.client.put('/api/settings',json={**config,'price_threshold':-2}).status_code,422)
 def test_price_thresholds_exclude_current_volume(self):
  r=evaluate_prices([100]*21+[106],[100]*21+[300],['2025-07-18']*22,{'price_threshold':5,'volume_threshold':2})
  self.assertEqual(r['change_pct'],6);self.assertEqual(r['volume_ratio'],3)
  self.assertTrue(r['price_alert'] and r['volume_alert']);self.assertIsNone(store.change(5,0))
  with self.assertRaises(ValueError):evaluate_prices([1],[2],['2025-01-01'],{})
 def test_network_links_explained(self):
  people=seed.contacts('TCS');self.assertEqual(people[0]['company'],'TCS')
  self.assertIn('Worked at TCS',people[0]['reason']);self.assertTrue(any(p['company']=='INFY' for p in people))
  self.assertEqual(seed.contacts('', 'semiconductors')[0]['company'],'DIXON')
 def test_job_and_document_boundary(self):
  d=store.rows("SELECT id FROM documents WHERE ticker='TCS'")[0]['id']
  r=self.client.post('/api/research',json={'ticker':'RELIANCE','question':'Explain revenue','document_id':d})
  self.assertEqual(r.status_code,404)
  r=self.client.post('/api/research',json={'ticker':'TCS','question':'Explain revenue and cash','document_id':d})
  self.assertEqual(r.status_code,200);jid=r.json()['job_id']
  for _ in range(100):
   job=self.client.get('/api/jobs/'+jid).json()
   if job['status'] in ('completed','failed'):break
   time.sleep(.02)
  self.assertEqual(job['status'],'completed',job);self.assertEqual(job['result']['scope'],'filing')
  self.assertTrue(job['result']['citations'])
  r=self.client.get(job['result']['citations'][0]['url'].split('#')[0])
  self.assertEqual(r.status_code,200);self.assertTrue(r.content.startswith(b'%PDF-'))
 def test_validation_and_origin(self):
  self.assertEqual(self.client.post('/api/portfolio',json={'ticker':'../../etc/passwd'}).status_code,400)
  self.assertEqual(self.client.post('/api/portfolio',json={'ticker':'SAFE'},headers={'Origin':'https://attacker.example'}).status_code,403)
  with self.assertRaises(ValueError):public_url('http://127.0.0.1')
  with self.assertRaises(ValueError):public_url('https://127.0.0.1')
  self.assertEqual(classify('Appointment of Chief Financial Officer')[0],'Management')
 def test_static_app(self):
  r=self.client.get('/');self.assertEqual(r.status_code,200)
  self.assertIn('Content-Security-Policy',r.headers);self.assertEqual(self.client.get('/static/app.js').status_code,200)
 def test_ai_reviewer_removes_unsupported_claim(self):
  import json
  self.fake_pdf('MODELTEST','annual_report','Revenue increased by 10 percent in FY2025. Cash flow remained positive. '*5)
  cid='S'+str(store.retrieve('MODELTEST','Explain revenue')[0]['id'])
  responses=[SimpleNamespace(output_text=json.dumps({'findings':[{'text':'Revenue increased by 10 percent in FY2025.','sources':[cid]},{'text':'Profit will triple next year.','sources':[cid]}],'limitations':[]})),SimpleNamespace(output_text=json.dumps({'checks':[{'index':0,'supported':True,'supports':[{'source':cid,'quote':'Revenue increased by 10 percent in FY2025.'}]},{'index':1,'supported':False,'reason':'No evidence supports the forecast.'}]}))]
  from unittest.mock import MagicMock
  client=MagicMock();client.responses.create.side_effect=responses
  with patch.dict(os.environ,{'OPENAI_API_KEY':'test-key'}),patch('openai.OpenAI',return_value=client):
   result=research('MODELTEST','Explain revenue')
  self.assertEqual(result['mode'],'ai');self.assertEqual(len(result['findings']),1)
  self.assertNotIn('triple',result['findings'][0]['text'])
  self.assertEqual(client.responses.create.call_count,2)
  self.assertFalse(client.responses.create.call_args.kwargs['store'])
 def test_ai_invalid_citations_fall_back_to_evidence(self):
  self.fake_pdf('BADMODEL','annual_report','Revenue increased. Cash flow remained positive throughout the reporting period. '*5)
  from unittest.mock import MagicMock
  client=MagicMock();client.responses.create.return_value=SimpleNamespace(output_text='{"findings":[{"text":"Invented result","sources":["S999999999"]}]}')
  with patch.dict(os.environ,{'OPENAI_API_KEY':'test-key'}),patch('openai.OpenAI',return_value=client):result=research('BADMODEL','Explain revenue')
  self.assertEqual(result['mode'],'evidence');self.assertTrue(result['citations'])
  self.assertTrue(any('failed validation' in l for l in result['limitations']))
 def test_source_failure_is_visible_and_preserves_archive(self):
  with patch('connectors.refresh_filings',side_effect=ConnectionError('unreachable')):
   jid=self.client.post('/api/refresh/filings').json()['job_id']
   for _ in range(100):
    result=self.client.get('/api/jobs/'+jid).json()
    if result['status']=='failed':break
    time.sleep(.02)
  self.assertEqual(result['status'],'failed')
  self.assertEqual(len(self.client.get('/api/events?mode=archive&days=365').json()['items']),5)
  self.assertEqual(self.client.get('/api/events?mode=live&days=1').json()['items'],[])

if __name__=='__main__':unittest.main(verbosity=2)
