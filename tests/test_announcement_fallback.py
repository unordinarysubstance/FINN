import json
import os
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import requests
import store,connectors,monitoring
from app import event_in_window

class AnnouncementFallbackTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.old=store.DATA;store.DATA=Path(self.temp.name);store.init(seed_demo=False)
  with store.db() as c:c.execute("INSERT INTO companies VALUES ('TCS','TCS','IT Services',1)")
  self.config=store.DATA/'sources.json';self.config.write_text(json.dumps({'sources':[{'ticker':'TCS','url':'https://example.org/announcements'}]}))
  self.env=patch.dict(os.environ,{'FINN_ANNOUNCEMENT_SOURCES':str(self.config)});self.env.start()
 def tearDown(self):
  self.env.stop();store.DATA=self.old;self.temp.cleanup()
 def test_publication_date_is_not_confused_with_reporting_date(self):
  html='<a href="a.pdf">Nov 01, 2026 Transcript for quarter ended September 30, 2026</a>'
  records=connectors.parse_company_announcements(html,'https://example.org/')
  self.assertEqual(len(records),1);self.assertEqual(records[0]['publication_date'],'2026-11-01')
  self.assertIn('September 30, 2026',records[0]['title'])
  self.assertEqual(connectors.parse_company_announcements('<a href="a.pdf">Results for quarter ended September 30, 2026</a>','https://example.org/'),[])
 def test_ambiguous_shared_parent_is_rejected(self):
  html='<div>Nov 01, 2026 <a href="a.pdf">A filing</a> Nov 02, 2026 <a href="b.pdf">Another filing</a></div>'
  self.assertEqual(connectors.parse_company_announcements(html,'https://example.org/'),[])
 def test_independent_primary_fallback_is_partial_and_idempotent(self):
  today=datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%b %d, %Y')
  html=f'<a href="report.pdf">{today} Consolidated financial results approved</a>'.encode()
  denied=requests.HTTPError(response=SimpleNamespace(status_code=403))
  with patch('connectors._refresh_nse_filings',side_effect=denied) as nse,patch('announcements.refresh_nse_rss',side_effect=ConnectionError()),patch('connectors.download',return_value=(html,'https://example.org/announcements')) as primary:
   first=monitoring.run_refresh('filings',30);second=monitoring.run_refresh('filings',30)
  self.assertEqual(nse.call_count,2);self.assertEqual(primary.call_count,2)
  self.assertEqual(first['status'],'partial');self.assertEqual(first['covered_tickers'],['TCS'])
  self.assertEqual(first['source_failures'][0]['code'],'access')
  self.assertEqual(first['added'],1);self.assertEqual(first['alerts_created'],1)
  self.assertEqual(second['added'],0);self.assertEqual(second['alerts_created'],0)
  self.assertEqual(store.rows('SELECT published_precision FROM event_metadata')[0]['published_precision'],'date')
  self.assertIsNone(monitoring.source_health()['filings']['last_success'])
 def test_no_provider_success_is_reported_as_failed(self):
  with patch('connectors._refresh_nse_filings',side_effect=ConnectionError()),patch('announcements.refresh_nse_rss',side_effect=ConnectionError()),patch('connectors.download',side_effect=ConnectionError()):r=monitoring.run_refresh('filings')
  self.assertEqual(r['status'],'failed');self.assertEqual(r['covered_tickers'],[])
  self.assertEqual(len(r['source_failures']),3)
 def test_date_only_event_overlaps_calendar_day_without_invented_time(self):
  start=datetime(2026,11,11,15,tzinfo=ZoneInfo('Asia/Kolkata'));end=start+timedelta(days=1)
  event={'published':'2026-11-11T00:00:00+05:30','published_precision':'date'}
  self.assertTrue(event_in_window(event,start,end))
  event['published_precision']='timestamp';self.assertFalse(event_in_window(event,start,end))
