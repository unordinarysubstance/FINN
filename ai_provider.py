"""Server-side model transport. Gemini is the default; providers never fail over."""
import os
import json
import re
import random
import time
import math
import threading
from types import SimpleNamespace
import httpx

class ModelOutputError(ValueError):
    """A fixed reason and metadata, never generated text or request contents."""
    def __init__(self,reason,*,finish_reason=None,block_reason=None,attempts=None):
        super().__init__('Model output failed validation.')
        self.validation_reason=reason
        self.finish_reason=finish_reason
        self.block_reason=block_reason
        self.attempts=attempts


_pace_lock=threading.Lock()
_next_request={}

def pace_request(model,deadline):
    interval=float(os.getenv('FINN_GEMINI_REQUEST_INTERVAL_SECONDS','15'))
    if not math.isfinite(interval) or not 0<=interval<=60:raise ValueError('Invalid Gemini request interval.')
    if not interval:return
    # One process/one configured project. Different API keys do not create extra
    # quota. Keep starts apart across both analyst/reviewer and concurrent jobs.
    with _pace_lock:
        now=time.monotonic()
        wait=max(0,_next_request.get(model,now)-now)
        if now+wait+1>=deadline:raise httpx.PoolTimeout('Gemini request pacing exhausted the time budget.')
        if wait:time.sleep(wait)
        _next_request[model]=time.monotonic()+interval


def minute_retry_delay(body):
    """Only a positively identified minute quota may receive one quota retry."""
    if not isinstance(body,dict) or not isinstance(body.get('error'),dict):return None
    error=body['error'];details=error.get('details',[])
    if error.get('code') in ('quota_exceeded','insufficient_quota','billing_hard_limit_reached','payment_required'):return None
    if not isinstance(details,list):details=[]
    scopes=[];delays=[]
    for detail in details:
        if not isinstance(detail,dict):continue
        if str(detail.get('@type','')).endswith('QuotaFailure'):
            for violation in detail.get('violations',[]):
                if isinstance(violation,dict):scopes.append(str(violation.get('quotaId','')).lower())
        if str(detail.get('@type','')).endswith('RetryInfo'):
            value=detail.get('retryDelay','')
            if isinstance(value,str) and re.fullmatch(r'\d+(?:\.\d+)?s',value):delays.append(float(value[:-1]))
    message=str(error.get('message','')).lower()
    # A daily exhaustion must never be retried, even if RetryInfo is also sent.
    if any('day' in scope or 'daily' in scope for scope in scopes) or re.search(r'per[ _-]*day|daily',message):return None
    minute=any('minute' in scope for scope in scopes) or bool(re.search(r'per[ _-]*minute',message))
    if not delays:
        match=re.search(r'retry in (\d+(?:\.\d+)?)s',message)
        if match:delays.append(float(match.group(1)))
    if minute and delays:
        value=max(delays)
        if not math.isfinite(value) or value>59:return None
        delay=math.ceil(value)+1
        if 0<delay<=60:return delay
    return None


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
        # Retry transient server failures and one explicitly timed minute limit.
        # Daily/unknown quota, auth and ambiguous transport failures stop.
        deadline=time.monotonic()+timeout
        minute_retried=False
        for attempt in range(1,max_attempts+1):
            try:
                pace_request(model,deadline)
                remaining=max(0.01,deadline-time.monotonic())
                response=httpx.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                                    headers={'x-goog-api-key':os.environ['GEMINI_API_KEY'].strip()},
                                    json=payload,timeout=httpx.Timeout(remaining,connect=min(10,remaining)),follow_redirects=False)
            except httpx.TimeoutException as exc:
                exc.attempts=attempt
                exc.timeout_seconds=timeout
                raise
            if attempt==max_attempts:return response,attempt
            if response.status_code==429 and not minute_retried:
                try:delay=minute_retry_delay(response.json())
                except ValueError:delay=None
                if delay is None or time.monotonic()+delay+1>=deadline:return response,attempt
                minute_retried=True
            elif response.status_code in (500,502,503,504):
                delay=2**(attempt-1)+random.uniform(0,0.25)
                retry_after=response.headers.get('retry-after','')
                if retry_after.isdigit():delay=max(delay,int(retry_after))
                if delay>8 or time.monotonic()+delay+1>=deadline:return response,attempt
            else:
                return response,attempt
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
            if not isinstance(body,dict):raise ModelOutputError('invalid_response',attempts=attempts)
            candidates=body.get('candidates',[])
            if not isinstance(candidates,list) or len(candidates)!=1 or not isinstance(candidates[0],dict):
                feedback=body.get('promptFeedback',{})
                raise ModelOutputError('missing_candidates',block_reason=feedback.get('blockReason') if isinstance(feedback,dict) else None,attempts=attempts)
            if candidates[0].get('finishReason')!='STOP':
                raise ModelOutputError('incomplete_output',finish_reason=candidates[0].get('finishReason'),attempts=attempts)
            # Never feed thought parts to the JSON parser or expose them in results.
            output=''.join(p['text'] for p in candidates[0].get('content',{}).get('parts',[])
                           if isinstance(p.get('text'),str) and not p.get('thought'))
            if not output.strip():raise ModelOutputError('empty_output',finish_reason='STOP',attempts=attempts)
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
