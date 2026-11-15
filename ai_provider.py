"""Server-side model transport. Gemini is the default; providers never fail over."""
import os
import json
import re
import random
import time
from types import SimpleNamespace
import httpx


def configuration():
    """Safe to expose in diagnostics: credentials are deliberately excluded."""
    provider=os.getenv('FINN_AI_PROVIDER','gemini').strip().lower()
    if provider=='gemini':
        model=os.getenv('FINN_GEMINI_MODEL','').strip() or 'gemini-3.6-flash'
        reviewer=os.getenv('FINN_GEMINI_REVIEW_MODEL','').strip() or model
        configured=bool(os.getenv('GEMINI_API_KEY','').strip())
        effort=''
    elif provider=='openai':
        model=os.getenv('FINN_MODEL','').strip() or 'gpt-4o-mini'
        reviewer=os.getenv('FINN_REVIEW_MODEL','').strip() or model
        configured=bool(os.getenv('OPENAI_API_KEY','').strip())
        effort=os.getenv('FINN_REVIEW_EFFORT','').strip() or ('low' if reviewer.startswith('gpt-6') else '')
    else:
        return {'provider':provider,'configured':False,'model':None,'review_model':None,'review_effort':''}
    return {'provider':provider,'configured':configured,'model':model,'review_model':reviewer,'review_effort':effort}


class GeminiError(Exception):
    def __init__(self,status_code,body,attempts=1):
        super().__init__('Gemini request failed.')
        self.status_code=status_code
        self.body=body
        self.attempts=attempts


class GeminiClient:
    """Map the two bounded JSON requests onto Gemini's generateContent REST API."""
    def __init__(self):
        self.responses=self

    def _request(self,model,payload,timeout,max_attempts=3):
        # Retry explicit server failures only. Quota/auth errors and ambiguous
        # transport failures do not trigger more requests or another provider.
        deadline=time.monotonic()+timeout
        for attempt in range(1,max_attempts+1):
            remaining=max(0.01,deadline-time.monotonic())
            try:
                response=httpx.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                                    headers={'x-goog-api-key':os.environ['GEMINI_API_KEY'].strip()},
                                    json=payload,timeout=httpx.Timeout(remaining,connect=min(10,remaining)),follow_redirects=False)
            except httpx.TimeoutException as exc:
                exc.attempts=attempt
                exc.timeout_seconds=timeout
                raise
            if response.status_code not in (500,502,503,504) or attempt==max_attempts:
                return response,attempt
            delay=2**(attempt-1)+random.uniform(0,0.25)
            # Honor a numeric Retry-After, without sleeping beyond this call's
            # budget. Long waits return the error for an explicit later retry.
            retry_after=response.headers.get('retry-after','')
            if retry_after.isdigit():delay=max(delay,int(retry_after))
            if delay>8 or time.monotonic()+delay+1>=deadline:return response,attempt
            response.close()
            time.sleep(delay)

    def create(self,*,model,instructions,input,text,max_output_tokens,timeout=None,max_attempts=3,**_):
        if not re.fullmatch(r'gemini-[A-Za-z0-9_.-]+',model):
            raise ValueError('Invalid Gemini model.')
        if timeout is None:timeout=gemini_timeout()
        if max_attempts not in (1,2,3):raise ValueError('Invalid attempt limit.')
        config={'responseMimeType':'application/json','maxOutputTokens':max_output_tokens}
        schema=text['format'].get('schema')
        if schema:config['responseJsonSchema']=schema
        if model.startswith(('gemini-3','gemini-4')):
            config['thinkingConfig']={'thinkingLevel':'LOW'}
        payload={'systemInstruction':{'parts':[{'text':instructions}]},
                 'contents':[{'role':'user','parts':[{'text':input}]}],
                 'generationConfig':config}
        # No key in the URL, redirects, tools, or search grounding.
        response,attempts=self._request(model,payload,timeout,max_attempts)
        try:
            try:body=response.json()
            except ValueError:body={}
            if response.status_code!=200:raise GeminiError(response.status_code,body,attempts)
            if not isinstance(body,dict):raise ValueError('Invalid Gemini response.')
            candidates=body.get('candidates',[])
            if len(candidates)!=1 or candidates[0].get('finishReason')!='STOP':
                raise ValueError('Incomplete model output.')
            # Never feed thought parts to the JSON parser or expose them in results.
            output=''.join(p['text'] for p in candidates[0].get('content',{}).get('parts',[])
                           if isinstance(p.get('text'),str) and not p.get('thought'))
            usage=body.get('usageMetadata',{})
            return SimpleNamespace(output_text=output,status='completed',attempts=attempts,usage=SimpleNamespace(
                input_tokens=usage.get('promptTokenCount'),
                output_tokens=usage.get('candidatesTokenCount',0)+usage.get('thoughtsTokenCount',0),
                total_tokens=usage.get('totalTokenCount')))
        finally:response.close()


def gemini_timeout():
    seconds=int(os.getenv('FINN_GEMINI_TIMEOUT_SECONDS','120'))
    if not 10<=seconds<=180:raise ValueError('Gemini timeout must be between 10 and 180 seconds.')
    return seconds


def check_ai():
    """Explicit CLI diagnostic: metadata plus one tiny generation per selected model.

    A listed model is not proof of free quota or current serving capacity.
    Never send company passages or contacts, or change the configured model.
    """
    from diagnostics import failure
    config=configuration()
    report={'provider':config['provider'],'model':config['model'],'review_model':config['review_model'],
            'status':'not_configured','available_flash_models':[],'probes':[],
            'note':'Model listing does not establish free-tier eligibility, remaining quota or serving capacity.'}
    if not config['configured']:return report
    if config['provider']!='gemini':
        report['status']='unsupported_provider'
        return report
    started=time.monotonic()
    try:
        page_token=None;models={}
        for _ in range(5):
            params={'pageSize':100}
            if page_token:params['pageToken']=page_token
            response=httpx.get('https://generativelanguage.googleapis.com/v1beta/models',
                headers={'x-goog-api-key':os.environ['GEMINI_API_KEY'].strip()},params=params,
                timeout=httpx.Timeout(15,connect=10),follow_redirects=False)
            try:
                try:body=response.json()
                except ValueError:body={}
                if response.status_code!=200:raise GeminiError(response.status_code,body)
                if not isinstance(body,dict):raise ValueError('Invalid model listing.')
                for item in body.get('models',[]):
                    name=item.get('name','').removeprefix('models/')
                    if re.fullmatch(r'gemini-[A-Za-z0-9_.-]+',name) and 'generateContent' in item.get('supportedGenerationMethods',[]):models[name]=item
                page_token=body.get('nextPageToken')
            finally:response.close()
            if not page_token:break
        report['model_listing_complete']=not bool(page_token)
        report['available_flash_models']=sorted(name for name in models if 'flash' in name)
        schema={'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok'],'additionalProperties':False}
        for model in dict.fromkeys((config['model'],config['review_model'])):
            probe={'model':model,'status':'not_listed'}
            if model in models:
                try:
                    result=GeminiClient().create(model=model,instructions='Return only the JSON object {"ok":true}.',
                        input='Return {"ok":true}.',text={'format':{'schema':schema}},max_output_tokens=1024,timeout=30,max_attempts=1)
                    if json.loads(result.output_text)!={'ok':True}:raise ValueError('Invalid probe output.')
                    probe.update(status='passed',attempts=result.attempts)
                except Exception as exc:probe.update(status='failed',error=failure(exc))
            report['probes'].append(probe)
        report['status']='passed' if all(p['status']=='passed' for p in report['probes']) else 'failed'
    except Exception as exc:
        report.update(status='failed',error=failure(exc))
    report['latency_ms']=round((time.monotonic()-started)*1000)
    return report


def client_for(config):
    if config['provider']=='gemini':return GeminiClient()
    if config['provider']=='openai':
        from openai import OpenAI
        return OpenAI(api_key=os.environ['OPENAI_API_KEY'],timeout=45,max_retries=0)
    raise ValueError('Unsupported model provider.')
