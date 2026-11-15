"""Offline Gemini HTTP transport and complete analyst/reviewer pipeline checks."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import httpx
import store
from ai_provider import configuration,GeminiClient,GeminiError
from diagnostics import failure
from research import research


def completion(payload,finish='STOP'):
    return httpx.Response(200,json={'candidates':[{'finishReason':finish,'content':{'parts':[
        {'text':'private thought, never output','thought':True},{'text':json.dumps(payload)}]}}],
        'usageMetadata':{'promptTokenCount':20,'candidatesTokenCount':10,'thoughtsTokenCount':5,'totalTokenCount':35}})


class GeminiTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'FINN_AI_PROVIDER':'gemini','GEMINI_API_KEY':'offline-gemini-key',
            'FINN_GEMINI_MODEL':'','FINN_GEMINI_REVIEW_MODEL':'',
            'OPENAI_API_KEY':'offline-openai-key','FINN_MODEL':'gpt-4o-mini','FINN_REVIEW_MODEL':'gpt-6.1-sol'})
        self.env.start()
        self.temp=tempfile.TemporaryDirectory();self.old=store.DATA;store.DATA=Path(self.temp.name)
        store.init(seed_demo=False)
        self.source='Consolidated results\nFY2026\nRevenue was 100 crore.\nOperating cash flow was 50 crore.'
        with patch.object(store,'PdfReader',return_value=SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda:self.source)])):
            store.import_pdf(b'%PDF-offline-gemini','GEMTEST','Annual report','annual_report','FY2026')
        self.cid='S'+str(store.retrieve('GEMTEST','revenue cash flow')[0]['id'])

    def tearDown(self):
        self.env.stop();store.DATA=self.old;self.temp.cleanup()

    def call(self):
        return GeminiClient().create(model='gemini-3.8-flash',instructions='Return JSON.',input='{}',
                                     text={'format':{'type':'json_object'}},max_output_tokens=1600)

    def test_default_ignores_legacy_openai_models_and_key(self):
        with patch.dict(os.environ,{'FINN_AI_PROVIDER':'','GEMINI_API_KEY':''}):
            # An invalid explicit selection also fails closed.
            self.assertFalse(configuration()['configured'])
        with patch.dict(os.environ):
            os.environ.pop('FINN_AI_PROVIDER',None)
            config=configuration()
        self.assertEqual(config['provider'],'gemini');self.assertEqual(config['model'],'gemini-3.8-flash')
        self.assertEqual(config['model'],config['review_model'])
        self.assertNotIn('offline-gemini-key',str(config))

    def test_missing_gemini_key_does_not_use_openai(self):
        with patch.dict(os.environ,{'GEMINI_API_KEY':''}),patch('openai.OpenAI') as paid,patch('ai_provider.httpx.post') as post:
            result=research('GEMTEST','revenue cash flow')
        self.assertEqual(result['mode'],'evidence');self.assertEqual(result['diagnostics']['fallback_code'],'not_configured')
        paid.assert_not_called();post.assert_not_called()

    def test_full_pipeline_sends_schema_copies_lines_and_reuses_cache(self):
        sent=[]
        def handler(request):
            self.assertEqual(request.url.host,'generativelanguage.googleapis.com')
            self.assertNotIn('offline-gemini-key',str(request.url))
            self.assertEqual(request.headers['x-goog-api-key'],'offline-gemini-key')
            self.assertTrue(str(request.url).endswith('/gemini-3.8-flash:generateContent'))
            body=json.loads(request.content);sent.append(body)
            self.assertNotIn('tools',body);self.assertNotIn('store',body)
            config=body['generationConfig'];self.assertEqual(config['responseMimeType'],'application/json')
            self.assertEqual(config['thinkingConfig'],{'thinkingLevel':'LOW'})
            self.assertEqual(config['maxOutputTokens'],8192)
            data=json.loads(body['contents'][0]['parts'][0]['text'])
            self.assertNotIn('contacts',data)
            if len(sent)==1:
                return completion({'findings':[{'text':'FY2026 consolidated revenue was 100 crore.','kind':'fact','sources':[self.cid]}],'limitations':[]})
            enum=config['responseJsonSchema']['properties']['checks']['items']['properties']['supports']['items']['properties']['source']['enum']
            self.assertEqual(enum,[self.cid])
            self.assertIn('3: Revenue was',data['claims'][0]['evidence'][0]['numbered_text'])
            return completion({'checks':[{'index':0,'supported':True,'text':'FY2026 consolidated revenue was 100 crore.','kind':'fact',
                'supports':[{'source':self.cid,'start_line':1,'end_line':3}],'reason':''}]})
        with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
            with patch('ai_provider.httpx.post',side_effect=transport.post),patch('openai.OpenAI') as paid:
                result=research('GEMTEST','revenue cash flow');cached=research('GEMTEST','revenue cash flow')
                # A model change must not reuse the other configuration's answer.
                with patch.dict(os.environ,{'FINN_GEMINI_MODEL':'gemini-offline-flash'}),patch('ai_provider.httpx.post',side_effect=httpx.ConnectError('offline')) as changed:
                    fresh=research('GEMTEST','revenue cash flow')
                self.assertEqual(changed.call_count,1);self.assertFalse(fresh['diagnostics']['cache_hit'])
        self.assertEqual(len(sent),2);paid.assert_not_called()
        self.assertEqual(result['mode'],'ai',result['diagnostics']);self.assertEqual(result['provider'],'gemini')
        self.assertEqual(result['findings'][0]['support_quotes'][0]['quote'],'\n'.join(self.source.splitlines()[:3]))
        self.assertEqual(result['diagnostics']['reviewer_usage'],{'input_tokens':20,'output_tokens':15,'total_tokens':35})
        self.assertTrue(cached['cached']);self.assertEqual(cached['findings'],result['findings'])
        self.assertNotIn('private thought',str(result))

    def test_quota_failure_is_redacted_without_retry_or_paid_fallback(self):
        error={'error':{'code':429,'status':'RESOURCE_EXHAUSTED','message':'Quota exceeded for offline-gemini-key'}}
        with patch('ai_provider.httpx.post',return_value=httpx.Response(429,json=error)) as post,patch('openai.OpenAI') as paid:
            result=research('GEMTEST','revenue cash flow')
        self.assertEqual(result['mode'],'evidence');self.assertEqual(post.call_count,1);paid.assert_not_called()
        diag=result['diagnostics'];self.assertEqual(diag['fallback_code'],'rate_limit')
        self.assertEqual(diag['error']['provider_status'],'RESOURCE_EXHAUSTED')
        self.assertNotIn('offline-gemini-key',str(diag));self.assertFalse(store.rows('SELECT * FROM cache'))

    def test_blocked_truncated_or_malformed_output_fails_validation(self):
        responses=[completion({},'MAX_TOKENS'),completion({},'SAFETY'),httpx.Response(200,json={'promptFeedback':{'blockReason':'SAFETY'}}),
                   httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'not json'}]}}]})]
        for response in responses:
            with self.subTest(response=response),patch('ai_provider.httpx.post',return_value=response):
                result=research('GEMTEST','revenue cash flow')
                self.assertEqual(result['mode'],'evidence');self.assertEqual(result['diagnostics']['fallback_code'],'validation')

    def test_reviewer_failure_does_not_publish_unreviewed_draft(self):
        draft=completion({'findings':[{'text':'Unsupported secret result','sources':[self.cid]}]})
        with patch('ai_provider.httpx.post',side_effect=[draft,httpx.Response(503,json={'error':{'message':'Unavailable'}})]):
            result=research('GEMTEST','revenue cash flow')
        self.assertTrue(result['diagnostics']['analyst_completed']);self.assertFalse(result['diagnostics']['reviewer_completed'])
        self.assertEqual(result['mode'],'evidence');self.assertNotIn('Unsupported secret result',str(result['findings']))

    def test_unknown_sources_and_wrong_source_lines_cannot_pass(self):
        cases=[({'findings':[{'text':'Invented','sources':['S9999999']}]},None),
               ({'findings':[{'text':'Revenue was 999 crore.','sources':[self.cid]}]},
                {'checks':[{'index':0,'supported':True,'text':'Revenue was 999 crore.','kind':'fact',
                 'supports':[{'source':self.cid,'start_line':1,'end_line':3}],'reason':''}]})]
        for draft,review in cases:
            with self.subTest(draft=draft):
                replies=[completion(draft)]+([completion(review)] if review else [])
                with patch('ai_provider.httpx.post',side_effect=replies):result=research('GEMTEST','revenue cash flow')
                if review:self.assertEqual(result['findings'],[])
                else:self.assertEqual(result['mode'],'evidence')
                self.assertEqual(result['diagnostics']['rejected_claims'],1)

    def test_model_path_is_validated_before_sending_credentials(self):
        with patch('ai_provider.httpx.post') as post:
            with self.assertRaises(ValueError):
                GeminiClient().create(model='https://other.example/',instructions='',input='',text={'format':{}},max_output_tokens=1)
        post.assert_not_called()

    def test_google_key_pattern_is_redacted_even_when_not_in_environment(self):
        report=failure(GeminiError(400,{'error':{'message':'Invalid key '+('AIza'+'syntheticfixture')+' https://example.org/?key=secret'}}))
        self.assertNotIn('syntheticfixture',str(report));self.assertNotIn('https://',str(report))
