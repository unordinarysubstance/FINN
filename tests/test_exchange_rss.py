from datetime import datetime,timedelta,timezone
from email.utils import format_datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import announcements as rss
import connectors,monitoring,store

class ExchangeRSSTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.old=store.DATA;store.DATA=Path(self.temp.name);store.init(seed_demo=False)
  with store.db() as c:
   c.execute("INSERT INTO companies VALUES ('TCS','Tata Consultancy Services','IT Services',1)")
   c.execute("INSERT INTO companies VALUES ('ITC','ITC','Consumer',1)")
  self.when=datetime.now(timezone.utc)-timedelta(minutes=5)
 def tearDown(self):store.DATA=self.old;self.temp.cleanup()
 def feed(self):
  return ('<rss><channel><item><title>Tata Consultancy Services Limited</title><link>https://nsearchives.nseindia.com/a.pdf</link><description>Quarterly financial results approved</description><pubDate>'+format_datetime(self.when)+'</pubDate></item><item><title>Other issuer</title><link>https://nsearchives.nseindia.com/ITC_123.pdf</link><description>Appointment of a director</description><pubDate>'+format_datetime(self.when)+'</pubDate></item></channel></rss>').encode()
 def test_feed_matches_exact_company_or_attachment_symbol_and_preserves_time(self):
  items,oldest,newest=rss.parse_feed(self.feed(),{'TCS':{'name':'Tata Consultancy Services'},'ITC':{'name':'ITC'}})
  self.assertEqual([i['ticker'] for i in items],['TCS','ITC']);self.assertEqual(oldest.replace(microsecond=0),self.when.replace(microsecond=0))
  self.assertEqual(items[0]['title'],'Quarterly financial results approved')
 def test_portfolio_feed_is_partial_alerting_is_idempotent(self):
  with patch('connectors._refresh_nse_filings',side_effect=ConnectionError()),patch('connectors.download',return_value=(self.feed(),rss.RSS_URL)):
   first=monitoring.run_refresh('filings',30);second=monitoring.run_refresh('filings',30)
  self.assertEqual(first['source'],'NSE RSS');self.assertEqual(first['status'],'partial');self.assertEqual(first['added'],2)
  self.assertEqual(first['alerts_created'],2);self.assertEqual(second['added'],0);self.assertEqual(second['alerts_created'],0)
  self.assertEqual(first['covered_tickers'],['ITC','TCS']);self.assertIn('bounded',first['coverage_notice'])
 def test_unparseable_dates_or_secondary_urls_do_not_become_events(self):
  raw=b'<rss><channel><item><symbol>TCS</symbol><link>https://news.example/a</link><pubDate>Thu, 12 Nov 2026 10:00:00 GMT</pubDate></item><item><symbol>TCS</symbol><link>https://nsearchives.nseindia.com/a.pdf</link><pubDate>unknown</pubDate></item></channel></rss>'
  self.assertEqual(rss.parse_feed(raw,{'TCS':{'name':'TCS'}})[0],[])
  with self.assertRaises(ValueError):rss.parse_feed(b'<html>blocked</html>',{})
  with self.assertRaises(ValueError):rss.parse_feed(b'<!DOCTYPE rss><rss/>',{})
 def test_same_filing_across_exchange_transports_does_not_duplicate(self):
  with patch('connectors.download',return_value=(self.feed(),rss.RSS_URL)):rss.refresh_nse_rss(30)
  before=len(store.rows('SELECT id FROM events'))
  added,ids=connectors.ingest_filings([{'symbol':'TCS','desc':'Quarterly financial results','an_dt':self.when.strftime('%d-%b-%Y %H:%M:%S'),'attchmntFile':'https://nsearchives.nseindia.com/a.pdf'}],{'TCS'})
  self.assertEqual(added,0);self.assertEqual(len(ids),1);self.assertEqual(len(store.rows('SELECT id FROM events')),before)
 def test_successful_recent_rss_still_supplements_configured_issuer_pages(self):
  rss_result={'source':'NSE RSS','partial':True,'added':0,'event_ids':[],'covered_tickers':[],'coverage_notice':'Bounded recent RSS only.'}
  company_result={'source':'Company IR','partial':True,'added':1,'event_ids':['issuer-event'],'covered_tickers':['TCS'],'source_failures':[]}
  with patch('connectors._refresh_nse_filings',side_effect=ConnectionError()),patch('announcements.refresh_nse_rss',return_value=rss_result),patch('connectors.refresh_company_filings',return_value=company_result) as supplement:
   result=connectors.refresh_filings(30)
  supplement.assert_called_once_with(30)
  self.assertEqual(result['source'],'NSE RSS + Company IR');self.assertEqual(result['event_ids'],['issuer-event'])
  self.assertEqual(result['added'],1);self.assertTrue(result['partial']);self.assertIn('completeness remains unverified',result['coverage_notice'])
 def test_issuer_failure_does_not_discard_successful_rss(self):
  rss_result={'source':'NSE RSS','partial':True,'added':0,'event_ids':[],'covered_tickers':[],'coverage_notice':'Bounded recent RSS only.'}
  with patch('connectors._refresh_nse_filings',side_effect=ConnectionError()),patch('announcements.refresh_nse_rss',return_value=rss_result),patch('connectors.refresh_company_filings',side_effect=ConnectionError()):result=connectors.refresh_filings(30)
  self.assertEqual(result['source'],'NSE RSS');self.assertEqual(len(result['source_failures']),2)
 def test_rss_and_issuer_page_same_attachment_keeps_one_event_and_timestamp(self):
  import json,os
  date=datetime.now().strftime('%b %d, %Y')
  config=store.DATA/'sources.json';config.write_text(json.dumps({'sources':[{'ticker':'TCS','url':'https://issuer.example/announcements'}]}))
  html=f'<a href="https://nsearchives.nseindia.com/a.pdf">{date} Quarterly financial results approved</a>'.encode()
  def fetch(url,*args,**kwargs):return (self.feed(),url) if url==rss.RSS_URL else (html,url)
  with patch.dict(os.environ,{'FINN_ANNOUNCEMENT_SOURCES':str(config)}),patch('connectors._refresh_nse_filings',side_effect=ConnectionError()),patch('connectors.download',side_effect=fetch):result=monitoring.run_refresh('filings',30)
  self.assertEqual(result['added'],2);self.assertEqual(result['alerts_created'],2)
  self.assertEqual(len(store.rows('SELECT id FROM events')),2)
  self.assertEqual(store.rows("SELECT published_precision FROM event_metadata WHERE source='NSE RSS'")[0]['published_precision'],'timestamp')
