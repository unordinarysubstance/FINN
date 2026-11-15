import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import requests
import acquisition as ac
import connectors
import store

class AcquisitionTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.old=store.DATA;store.DATA=Path(self.temp.name);store.init(seed_demo=False)
  self.env=patch.dict(os.environ,{'FINN_AI_PROVIDER':'openai','GEMINI_API_KEY':'','OPENAI_API_KEY':'','FINN_DISABLE_MONITOR':'1'});self.env.start()
  self.company={'company_name':'Unseen Industries Limited','isin':'INE000A01001'}
  self.profile={'ticker':'UNSEEN','company_name':'Unseen Industries Ltd','exchange_link_verified':True,'website':'https://issuer.example','discovery_url':'https://www.screener.in/company/UNSEEN/','documents':[
   {'kind':kind,'url':'https://issuer.example/'+name+'.pdf','title':name,'discovery_url':'https://www.screener.in/company/UNSEEN/'} for kind,name in [('annual_report','annual'),('transcript','q2'),('transcript','q1')]]}
  self.texts={'annual':'Unseen Industries Limited\nIntegrated Annual Report\n2025-26\nRevenue and cash flow from business segments. '*15,
   'q2':'Unseen Industries Limited\nQ2 FY2027 Earnings Call Transcript\nManagement says demand and revenue are growing. '*15,
   'q1':'Unseen Industries Limited\nQ1 FY2027 Earnings Call Transcript\nManagement says demand and revenue are growing. '*15}
 def tearDown(self):self.env.stop();store.DATA=self.old;self.temp.cleanup()
 def reader(self,content):
  if hasattr(content,'getvalue'):content=content.getvalue()
  text=content.decode().removeprefix('%PDF-');return SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda:text)])
 def fetch(self,url,max_bytes=None):return ('%PDF-'+self.texts[url.rsplit('/',1)[-1].split('.')[0]]).encode(),url
 def contexts(self):
  from contextlib import ExitStack
  stack=ExitStack()
  stack.enter_context(patch('acquisition.connectors.discover_profile',return_value=self.profile))
  stack.enter_context(patch('acquisition.directory_identity',return_value=self.company))
  stack.enter_context(patch('acquisition.connectors.download',side_effect=self.fetch))
  stack.enter_context(patch('acquisition.PdfReader',side_effect=self.reader))
  stack.enter_context(patch('store.PdfReader',side_effect=self.reader))
  return stack
 def test_unseeded_ticker_acquires_sources_and_researches_without_joining_portfolio(self):
  stages=[]
  with self.contexts():result=ac.acquire_and_research('UNSEEN','What drives revenue and cash flow?',progress=lambda stage,message:stages.append(stage))
  self.assertEqual(result['acquisition']['status'],'ready');self.assertEqual(result['mode'],'evidence')
  self.assertTrue(result['citations']);self.assertEqual(result['coverage']['annual_reports'],1);self.assertEqual(result['coverage']['transcripts'],2)
  self.assertEqual(store.rows("SELECT portfolio FROM companies WHERE ticker='UNSEEN'")[0]['portfolio'],0)
  self.assertIn('downloading',stages);self.assertIn('indexing',stages);self.assertEqual(stages[-1],'analysing')
  self.assertTrue(all(d['verification']=='automatic_content_checks' for d in result['documents']))
  with patch('acquisition.connectors.discover_profile') as discover:second=ac.acquire('UNSEEN')
  discover.assert_not_called();self.assertEqual(second['status'],'existing');self.assertEqual(len(store.rows('SELECT * FROM documents')),3)
 def test_bad_company_type_and_unverified_period_never_enter_corpus(self):
  self.texts={'annual':'Another Issuer Limited Annual Report 2025-26', 'q2':'Unseen Industries Limited Q2 FY2027 investor presentation', 'q1':'Unseen Industries Limited Earnings Call Transcript July 2026'}
  self.profile['website']=None
  for item in self.profile['documents']:item['url']=item['url'].replace('issuer.example','www.bseindia.com')
  with self.contexts():result=ac.acquire('UNSEEN')
  self.assertEqual(result['status'],'unavailable');self.assertFalse(store.rows('SELECT * FROM documents'))
  self.assertEqual(len(result['failures']),3)
 def test_failure_is_cached_and_explicit_retry_bypasses_cooldown(self):
  with patch('acquisition.connectors.discover_profile',side_effect=requests.ConnectionError('private diagnostic')) as discover:
   first=ac.acquire('UNSEEN');second=ac.acquire('UNSEEN');third=ac.acquire('UNSEEN',force=True)
  self.assertEqual(discover.call_count,2);self.assertTrue(second['cached_attempt']);self.assertEqual(first['status'],'unavailable')
  self.assertNotIn('private diagnostic',json.dumps(third));self.assertEqual(first['failures'][0]['code'],'connectivity')
 def test_exchange_link_fallback_when_directory_is_down(self):
  with self.contexts(),patch('acquisition.directory_identity',side_effect=requests.ConnectionError()):r=ac.acquire('UNSEEN')
  self.assertEqual(r['status'],'ready');self.assertIn('exact NSE',r['identity_source'])
 def test_unverified_ticker_is_not_added(self):
  self.profile['exchange_link_verified']=False
  with self.contexts(),patch('acquisition.directory_identity',return_value=None):r=ac.acquire('UNSEEN')
  self.assertEqual(r['status'],'unavailable');self.assertFalse(store.rows('SELECT * FROM companies'))
 def test_issuer_site_fallback_after_exchange_download_failure(self):
  self.profile['documents']=[{'kind':'annual_report','url':'https://www.bseindia.com/blocked.pdf','discovery_url':'https://www.screener.in/company/UNSEEN/','title':'annual'}]
  def fetch(url,max_bytes=None):
   if 'bseindia' in url:raise requests.HTTPError('blocked')
   if url=='https://issuer.example':return b'<a href="/investors">Investors</a>',url
   if url.endswith('/investors'):return b'<a href="/annual.pdf">Annual report</a><a href="/q2.pdf">Q2 transcript</a><a href="/q1.pdf">Q1 transcript</a>',url
   return self.fetch(url,max_bytes)
  with self.contexts(),patch('acquisition.connectors.download',side_effect=fetch):r=ac.acquire('UNSEEN')
  self.assertEqual(r['status'],'ready');self.assertEqual(len(r['documents']),3);self.assertEqual(len(r['failures']),1)
 def test_secondary_host_is_never_downloaded(self):
  self.profile['website']=None
  with self.contexts(),patch('acquisition.connectors.download') as fetch:r=ac.acquire('UNSEEN')
  fetch.assert_not_called();self.assertEqual(r['status'],'unavailable')
 def test_reporting_period_comes_from_pdf_not_discovery_date(self):
  self.assertEqual(ac.reporting_period('annual_report',['Annual Report 2024–25']),'FY2025')
  self.assertEqual(ac.reporting_period('transcript',['Q1 FY26 Transcript']),'Q1 FY2026')
  self.assertEqual(ac.reporting_period('transcript',['Q2 FY2025-26 Transcript']),'Q2 FY2026')
  self.assertEqual(ac.reporting_period('transcript',['Q1 2025 - 2026 Media & Analyst Call Transcript']),'Q1 FY2026')
  self.assertEqual(ac.reporting_period('annual_report',['Integrated Annual Report 2 0 2 5- 2 6']),'FY2026')
  with self.assertRaises(ac.SourceValidation):ac.reporting_period('transcript',['Earnings Call July 2026'])
 def test_directory_bom_spacing_and_cache(self):
  raw=b'\xef\xbb\xbfSYMBOL, NAME OF COMPANY, ISIN NUMBER\nUNSEEN,Unseen Industries Limited,INE000A01001\n'
  with patch('acquisition.connectors.download',return_value=(raw,ac.DIRECTORY_URL)) as fetch:
   self.assertEqual(ac.directory_identity('UNSEEN'),self.company);self.assertEqual(ac.directory_identity('UNSEEN'),self.company)
  fetch.assert_called_once()
 def test_profile_checks_exact_nse_quote_symbol_and_encodes_ampersand(self):
  html=b'<h1>Mahindra &amp; Mahindra Ltd</h1><a href="https://www.nseindia.com/get-quotes/equity?symbol=M%26M">NSE</a><a href="https://www.mahindra.com">Website</a>'
  with patch('connectors.download',return_value=(html,'https://www.screener.in/company/M%26M/')) as fetch:r=connectors.discover_profile('M&M')
  self.assertTrue(r['exchange_link_verified']);self.assertIn('M%26M',fetch.call_args.args[0])
  with patch('connectors.download',return_value=(html,'https://www.screener.in/company/M%26M/')):self.assertFalse(connectors.discover_profile('OTHER')['exchange_link_verified'])
 def test_blocked_screener_uses_quote_metadata_only_to_locate_issuer(self):
  info={'symbol':'UNSEEN.NS','quoteType':'EQUITY','longName':'Unseen Industries Limited','website':'https://issuer.example','brokerOpinion':'must never become research evidence'}
  with patch('connectors._screener_profile',side_effect=requests.ConnectionError()),patch('yfinance.Ticker') as quote:
   quote.return_value.get_info.return_value=info;r=connectors.discover_profile('UNSEEN')
  self.assertTrue(r['quote_verified']);self.assertEqual(r['documents'],[]);self.assertNotIn('brokerOpinion',r)
  self.assertEqual(r['website'],'https://issuer.example');self.assertEqual(r['source_failures'][0]['code'],'connectivity')
 def test_standalone_directory_fallback_is_only_used_for_missing_consolidated_page(self):
  response=SimpleNamespace(status_code=404)
  html=b'<h1>Unseen Industries Ltd</h1>'
  with patch('connectors.download',side_effect=[requests.HTTPError(response=response),(html,'https://www.screener.in/company/UNSEEN/')]) as download:r=connectors._screener_profile('UNSEEN')
  self.assertEqual(download.call_count,2);self.assertTrue(download.call_args.args[0].endswith('/UNSEEN/'))
 def test_api_defaults_to_acquisition_and_reports_job_stages(self):
  from app import app
  from fastapi.testclient import TestClient
  client=TestClient(app)
  with self.contexts():
   response=client.post('/api/research',json={'ticker':'UNSEEN','question':'Explain revenue and cash flow'})
   for _ in range(100):
    job=client.get('/api/jobs/'+response.json()['job_id']).json()
    if job['status'] in ('completed','failed'):break
    time.sleep(.02)
  self.assertEqual(job['status'],'completed',job);self.assertEqual(job['result']['acquisition']['status'],'ready');self.assertTrue(job['result']['citations'])
 def test_filing_scope_never_fetches_other_documents(self):
  with patch('acquisition.acquire') as acquire,patch('research.research',return_value={'limitations':[]}) as research:
   ac.acquire_and_research('UNSEEN','Explain revenue','filing-id')
  acquire.assert_not_called();research.assert_called_once_with('UNSEEN','Explain revenue','filing-id',None)
 def test_encoded_viewer_link_resolves_without_downloading_html(self):
  viewer='https://issuer.example/pdf-viewer?pdf=%2Fq2.pdf'
  with patch('acquisition.connectors.download',return_value=(b'%PDF-real-document','https://issuer.example/q2.pdf')) as download:
   content,url=ac.download_primary_pdf(viewer,'https://issuer.example','transcript')
  self.assertEqual(content,b'%PDF-real-document');self.assertEqual(url,'https://issuer.example/q2.pdf')
  download.assert_called_once_with('https://issuer.example/q2.pdf',max_bytes=store.pdf_limit('transcript'))
 def test_embedded_primary_pdf_and_issuer_link_discovery(self):
  html=b'<iframe src="/document.pdf"></iframe>'
  with patch('acquisition.connectors.download',side_effect=[(html,'https://issuer.example/viewer'),(b'%PDF-content','https://issuer.example/document.pdf')]) as download:
   self.assertEqual(ac.download_primary_pdf('https://issuer.example/viewer','https://issuer.example','transcript')[0],b'%PDF-content')
  self.assertEqual(download.call_count,2)
  found,_=ac.issuer_links(b'<a href="/pdf-viewer?pdf=%2FTranscript_Q2.pdf">View</a>','https://issuer.example/investors','https://issuer.example')
  self.assertEqual(found[0]['kind'],'transcript');self.assertIn('pdf-viewer',found[0]['url'])
 def test_viewer_cannot_delegate_to_secondary_or_private_host_or_credentials(self):
  from urllib.parse import urlunsplit
  # Synthetic userinfo exists only to assert that the resolver rejects it.
  with_userinfo=urlunsplit(('https','user:password@issuer.example','/report.pdf','',''))
  for target in ('https://other.example/report.pdf','https://127.0.0.1/report.pdf','http://issuer.example/report.pdf',with_userinfo,'https://issuer.example:8443/report.pdf'):
   with self.subTest(target=target),patch('acquisition.connectors.download') as download:
    from urllib.parse import quote
    with self.assertRaises(ac.SourceValidation):ac.download_primary_pdf('https://issuer.example/viewer?file='+quote(target,safe=''),'https://issuer.example','transcript')
    download.assert_not_called()
 def test_ambiguous_viewer_targets_are_rejected(self):
  with self.assertRaises(ac.SourceValidation):ac.viewer_target('https://issuer.example/viewer?pdf=/one.pdf&file=/two.pdf','https://issuer.example')
  with patch('acquisition.connectors.download',return_value=(b'<iframe src="/one.pdf"></iframe><object data="/two.pdf"></object>','https://issuer.example/viewer')):
   with self.assertRaises(ac.SourceValidation):ac.download_primary_pdf('https://issuer.example/viewer','https://issuer.example','transcript')
 def test_geographic_brand_variant_only_on_issuer_hosted_pdf(self):
  body=b'%PDF-Unseen Industries Q1 FY27 Earnings Call Transcript. Management says revenue and cash flow improved.'
  company={'company_name':'Unseen Industries India Limited'}
  with patch('acquisition.PdfReader',side_effect=self.reader):
   with self.assertRaises(ac.SourceValidation):ac.inspect_pdf(body,company,'transcript')
   self.assertEqual(ac.inspect_pdf(body,company,'transcript',issuer_hosted=True),'Q1 FY2027')
   with self.assertRaises(ac.SourceValidation):ac.inspect_pdf(body,{'company_name':'Another Issuer India Limited'},'transcript',issuer_hosted=True)
 def test_acquisition_pipeline_imports_primary_pdfs_behind_viewer_urls(self):
  self.profile['documents'][1]['url']='https://issuer.example/pdf-viewer?pdf=%2Fq2.pdf'
  self.profile['documents'][2]['url']='https://issuer.example/pdf-viewer?pdf=%2Fq1.pdf'
  with self.contexts():r=ac.acquire('UNSEEN')
  self.assertEqual(r['status'],'ready')
  self.assertEqual({d['period'] for d in r['documents']},{'FY2026','Q1 FY2027','Q2 FY2027'})
  self.assertTrue(all('pdf-viewer' not in d['url'] for d in r['documents']))
