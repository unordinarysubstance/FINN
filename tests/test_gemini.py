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
from ai_provider import configuration,GeminiClient,GeminiError,check_ai,gemini_timeout
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
            'FINN_GEMINI_TIMEOUT_SECONDS':'120',
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
        return GeminiClient().create(model='gemini-3.6-flash',instructions='Return JSON.',input='{}',
                                     text={'format':{'type':'json_object'}},max_output_tokens=1600)

    def test_default_ignores_legacy_openai_models_and_key(self):
        with patch.dict(os.environ,{'FINN_AI_PROVIDER':'','GEMINI_API_KEY':''}):
            # An invalid explicit selection also fails closed.
            self.assertFalse(configuration()['configured'])
        with patch.dict(os.environ):
            os.environ.pop('FINN_AI_PROVIDER',None)
            config=configuration()
        self.assertEqual(config['provider'],'gemini');self.assertEqual(config['model'],'gemini-3.6-flash')
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
            self.assertTrue(str(request.url).endswith('/gemini-3.6-flash:generateContent'))
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
        errors=[httpx.Response(503,json={'error':{'message':'Unavailable'}}) for _ in range(3)]
        with patch('ai_provider.time.sleep'),patch('ai_provider.httpx.post',side_effect=[draft]+errors) as post:
            result=research('GEMTEST','revenue cash flow')
        self.assertTrue(result['diagnostics']['analyst_completed']);self.assertFalse(result['diagnostics']['reviewer_completed'])
        self.assertEqual(result['mode'],'evidence');self.assertNotIn('Unsupported secret result',str(result['findings']))
        self.assertEqual(post.call_count,4);self.assertEqual(result['diagnostics']['error']['attempts'],3)

    def test_transient_overload_retries_same_payload_and_reports_attempts(self):
        responses=[httpx.Response(503,json={'error':{'status':'UNAVAILABLE'}}),
                   httpx.Response(502,text='Bad gateway'),completion({'findings':[]})]
        with patch('ai_provider.httpx.post',side_effect=responses) as post,patch('ai_provider.time.sleep') as sleep,patch('ai_provider.random.uniform',return_value=0):
            result=self.call()
        self.assertEqual(result.attempts,3);self.assertEqual(result.output_text,'{"findings": []}')
        self.assertEqual([c.args[0] for c in sleep.call_args_list],[1,2])
        self.assertEqual(post.call_count,3)
        bodies=[c.kwargs['json'] for c in post.call_args_list]
        self.assertTrue(all(body==bodies[0] for body in bodies))
        self.assertTrue(all(response.is_closed for response in responses))

    def test_persistent_overload_stops_after_three_attempts(self):
        errors=[httpx.Response(503,json={'error':{'status':'UNAVAILABLE','message':'High demand'}}) for _ in range(3)]
        with patch('ai_provider.httpx.post',side_effect=errors) as post,patch('ai_provider.time.sleep') as sleep,patch('openai.OpenAI') as paid:
            result=research('GEMTEST','revenue cash flow')
        self.assertEqual(post.call_count,3);self.assertEqual(sleep.call_count,2);paid.assert_not_called()
        self.assertEqual(result['mode'],'evidence')
        self.assertEqual(result['diagnostics']['fallback_code'],'temporarily_unavailable')
        self.assertEqual(result['diagnostics']['error']['attempts'],3)
        self.assertFalse(store.rows('SELECT * FROM cache'))
        self.assertTrue(all(response.is_closed for response in errors))

    def test_client_errors_and_ambiguous_timeouts_are_not_retried(self):
        for status in (400,401,403,404,429):
            with self.subTest(status=status),patch('ai_provider.httpx.post',return_value=httpx.Response(status,json={})) as post,patch('ai_provider.time.sleep') as sleep:
                with self.assertRaises(GeminiError):self.call()
                self.assertEqual(post.call_count,1);sleep.assert_not_called()
        with patch('ai_provider.httpx.post',side_effect=httpx.ReadTimeout('response may already have generated')) as post:
            with self.assertRaises(httpx.ReadTimeout):self.call()
            self.assertEqual(post.call_count,1)

    def test_long_retry_after_returns_without_retry(self):
        for seconds in ('10','120'):
            with self.subTest(seconds=seconds):
                response=httpx.Response(503,json={},headers={'retry-after':seconds})
                with patch('ai_provider.httpx.post',return_value=response) as post,patch('ai_provider.time.sleep') as sleep:
                    with self.assertRaises(GeminiError) as error:self.call()
                self.assertEqual(error.exception.attempts,1);self.assertEqual(post.call_count,1);sleep.assert_not_called()

    def test_retry_does_not_reset_time_budget(self):
        replies=[httpx.Response(503,json={}),completion({})]
        with patch('ai_provider.httpx.post',side_effect=replies) as post,patch('ai_provider.time.sleep'),patch('ai_provider.random.uniform',return_value=0),patch('ai_provider.time.monotonic',side_effect=[0,0,1,3]):
            self.call()
        self.assertEqual([c.kwargs['timeout'].read for c in post.call_args_list],[120,117])

    def test_timeout_configuration_is_bounded(self):
        self.assertEqual(gemini_timeout(),120)
        for value in ('10','180'):
            with patch.dict(os.environ,{'FINN_GEMINI_TIMEOUT_SECONDS':value}):self.assertEqual(gemini_timeout(),int(value))
        for value in ('0','181','not-a-number'):
            with patch.dict(os.environ,{'FINN_GEMINI_TIMEOUT_SECONDS':value}):
                with self.assertRaises(ValueError):gemini_timeout()

    def test_timeout_reports_attempt_and_budget_without_retry(self):
        with patch('ai_provider.httpx.post',side_effect=httpx.ReadTimeout('private transport details')) as post:
            result=research('GEMTEST','revenue cash flow')
        diag=result['diagnostics']
        self.assertEqual(post.call_count,1);self.assertEqual(diag['failed_stage'],'analyst')
        self.assertEqual(diag['request_timeout_seconds'],120);self.assertEqual(diag['error']['timeout_seconds'],120)
        self.assertEqual(diag['error']['attempts'],1);self.assertEqual(diag['fallback_code'],'timeout')
        self.assertNotIn('private transport details',str(result))

    def test_check_ai_lists_models_and_uses_one_tiny_probe_without_company_data(self):
        metadata=[httpx.Response(200,json={'models':[{'name':'models/gemini-3.6-flash','supportedGenerationMethods':['generateContent']}],'nextPageToken':'next-offline-page'}),
                  httpx.Response(200,json={'models':[{'name':'models/gemini-offline-flash','supportedGenerationMethods':['generateContent']}]})]
        with patch('ai_provider.httpx.get',side_effect=metadata) as get,patch('ai_provider.httpx.post',return_value=completion({'ok':True})) as post:
            report=check_ai()
        self.assertEqual(report['status'],'passed');self.assertTrue(report['model_listing_complete'])
        self.assertEqual(get.call_count,2);self.assertEqual(post.call_count,1)
        self.assertEqual(get.call_args.kwargs['params']['pageToken'],'next-offline-page')
        body=post.call_args.kwargs['json']
        self.assertEqual(body['generationConfig']['maxOutputTokens'],1024)
        self.assertLessEqual(post.call_args.kwargs['timeout'].read,30)
        self.assertNotIn('GEMTEST',str(body));self.assertNotIn('Revenue',str(body));self.assertNotIn('contacts',str(body))
        self.assertNotIn('offline-gemini-key',str(report))
        self.assertEqual(report['available_flash_models'],['gemini-3.6-flash','gemini-offline-flash'])
        self.assertFalse(store.rows('SELECT * FROM cache'))

    def test_check_ai_missing_key_does_not_make_requests(self):
        with patch.dict(os.environ,{'GEMINI_API_KEY':''}),patch('ai_provider.httpx.get') as get,patch('ai_provider.httpx.post') as post:
            report=check_ai()
        self.assertEqual(report['status'],'not_configured');get.assert_not_called();post.assert_not_called()

    def test_check_ai_does_not_probe_or_replace_an_unlisted_model(self):
        metadata=httpx.Response(200,json={'models':[{'name':'models/gemini-other-flash','supportedGenerationMethods':['generateContent']}]})
        with patch('ai_provider.httpx.get',return_value=metadata),patch('ai_provider.httpx.post') as post:
            report=check_ai()
        self.assertEqual(report['status'],'failed');self.assertEqual(report['probes'][0]['status'],'not_listed')
        self.assertEqual(report['model'],'gemini-3.6-flash');post.assert_not_called()

    def test_check_ai_overload_does_not_retry_or_claim_a_success(self):
        metadata=httpx.Response(200,json={'models':[{'name':'models/gemini-3.6-flash','supportedGenerationMethods':['generateContent']}]})
        with patch('ai_provider.httpx.get',return_value=metadata),patch('ai_provider.httpx.post',return_value=httpx.Response(503,json={})) as post:
            report=check_ai()
        self.assertEqual(report['status'],'failed');self.assertEqual(post.call_count,1)
        self.assertEqual(report['probes'][0]['error']['code'],'temporarily_unavailable')

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
