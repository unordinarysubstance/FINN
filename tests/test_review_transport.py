"""Exercise the installed OpenAI SDK through an HTTP transport with no network."""
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import httpx
from openai import OpenAI
import store
from research import research

class ReviewTransportTests(unittest.TestCase):
 def test_sdk_sends_actual_source_enum_and_returns_line_selected_support(self):
  temp=tempfile.TemporaryDirectory();old=store.DATA;store.DATA=Path(temp.name)
  try:
   store.init(seed_demo=False)
   with store.db() as c:
    c.execute("INSERT INTO chunks(id,document_id,page,text) VALUES (1000,NULL,1,'unused')")
   source='Consolidated Statement of Cash Flows\nFY2026\nProfit for the year 49,454 48,797\nTaxes paid (14,384) (15,586)\nNet cash flows generated from operating activities 52,094 48,908'
   with patch.object(store,'PdfReader',return_value=SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda:source)])):
    store.import_pdf(b'%PDF-offline-fixture','SDKTEST','Annual report','annual_report','FY2026')
   cid='S'+str(store.retrieve('SDKTEST','operating cash flow and profit')[0]['id'])
   self.assertNotEqual(cid,'S1');requests=[]
   def handler(request):
    body=json.loads(request.content);requests.append(body)
    if len(requests)==1:
     self.assertEqual(body['model'],'gpt-4o-mini')
     payload={'findings':[{'text':'FY2026 consolidated profit was 49,454 crore and net operating cash flow was 52,094 crore.','sources':[cid]}],'limitations':['No forward-looking explicit guidance was provided.']}
    else:
     self.assertEqual(body['model'],'gpt-6.1-sol');self.assertEqual(body['reasoning']['effort'],'low')
     fmt=body['text']['format'];self.assertEqual(fmt['type'],'json_schema');self.assertTrue(fmt['strict'])
     enum=fmt['schema']['properties']['checks']['items']['properties']['supports']['items']['properties']['source']['enum']
     self.assertEqual(enum,[cid])
     evidence=json.loads(body['input'])['claims'][0]['evidence'][0]
     self.assertEqual(evidence['id'],cid);self.assertIn('3: Profit for the year',evidence['numbered_text'])
     payload={'checks':[{'index':0,'supported':True,'text':'FY2026 consolidated profit was 49,454 crore and net operating cash flow was 52,094 crore.','kind':'fact','supports':[{'source':cid,'start_line':1,'end_line':3},{'source':cid,'start_line':5,'end_line':5}],'reason':''}]}
    response={'id':'resp_offline','object':'response','created_at':0,'status':'completed','model':'gpt-4o-mini','output':[{'id':'msg_offline','type':'message','role':'assistant','status':'completed','content':[{'type':'output_text','text':json.dumps(payload),'annotations':[]}]}],'usage':{'input_tokens':1,'output_tokens':1,'total_tokens':2}}
    return httpx.Response(200,json=response)
   with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
    with OpenAI(api_key='offline-test-key',http_client=transport) as client:
     with patch.dict(os.environ,{'FINN_AI_PROVIDER':'openai','GEMINI_API_KEY':'','OPENAI_API_KEY':'offline-test-key','FINN_MODEL':'gpt-4o-mini','FINN_REVIEW_MODEL':'gpt-6.1-sol','FINN_REVIEW_EFFORT':'low'}),patch('openai.OpenAI',return_value=client):
      result=research('SDKTEST','operating cash flow and profit')
      self.assertNotIn('No forward-looking explicit guidance was provided.',result['limitations'])
      with store.db() as c:
       row=c.execute('SELECT key,result FROM cache').fetchone();legacy=json.loads(row['result'])
       legacy['limitations']=['No forward-looking explicit guidance was provided.']
       c.execute('UPDATE cache SET result=? WHERE key=?',(json.dumps(legacy),row['key']))
      cached=research('SDKTEST','operating cash flow and profit')
      self.assertTrue(cached['cached']);self.assertEqual(cached['findings'],result['findings'])
      self.assertEqual(cached['limitations'],result['limitations'])
   self.assertEqual(len(requests),2);self.assertEqual(result['mode'],'ai',result['diagnostics'])
   self.assertEqual(len(result['findings']),1)
   self.assertEqual(result['findings'][0]['support_quotes'][1]['quote'],'Net cash flows generated from operating activities 52,094 48,908')
  finally:store.DATA=old;temp.cleanup()
