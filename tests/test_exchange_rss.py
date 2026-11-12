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
