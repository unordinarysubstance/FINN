import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest
import store
import connectors
import manage
import json

class DocumentLimitTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.old=store.DATA;store.DATA=Path(self.temp.name);store.init(seed_demo=False)
 def tearDown(self):
  store.DATA=self.old;self.temp.cleanup()
 def test_large_annual_report_allowed_but_transcript_rejected(self):
  # Exercise a real payload just above the old cap without a costly PDF fixture.
  data=b'%PDF-1.4\n'+b' '*(26*1024*1024)
  reader=SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda:'Annual report business revenue cash flow for the company. '*4)])
  with patch.object(store,'PdfReader',return_value=reader):
   doc=store.import_pdf(data,'TEST','Annual report','annual_report','FY2026')
  self.assertEqual(store.rows('SELECT kind FROM documents WHERE id=?',(doc,))[0]['kind'],'annual_report')
  with self.assertRaisesRegex(ValueError,'25 MB'):store.import_pdf(data,'TEST','Transcript','transcript')
 def test_download_stops_at_explicit_cap(self):
  response=SimpleNamespace(status_code=200,raise_for_status=lambda:None,iter_content=lambda size:iter([b'%PDF-',b'x'*20,b'x'*20]))
  class Context:
   def __enter__(self):return response
   def __exit__(self,*args):pass
  with patch('connectors.public_url'),patch('connectors.requests.get',return_value=Context()):
   with self.assertRaisesRegex(ValueError,'size limit'):connectors.download('https://example.org/a.pdf',max_bytes=32)
 def test_preparation_uses_annual_limit_for_remote_download(self):
  item=dict(ticker='TEST',company_name='Test Limited',title='Annual',kind='annual_report',period='FY2026',url='https://example.org/a.pdf',discovery_url='https://example.org/ir',identity_status='content_verified')
  manifest=Path(self.temp.name)/'manifest.json';manifest.write_text(json.dumps({'documents':[item]}))
  with patch('manage.connectors.download',return_value=(b'%PDF-test',item['url'])) as fetch,patch('manage.validate_identity'),patch('manage.store.import_pdf',return_value='doc'):
   result=manage.prepare(manifest)
  self.assertEqual(result['documents'][0]['status'],'indexed')
  self.assertEqual(fetch.call_args.kwargs['max_bytes'],100*1024*1024)
