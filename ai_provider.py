"""Server-side model transport. Gemini is the default; providers never fail over."""
import os
import re
import random
import time
from types import SimpleNamespace
import httpx


def configuration():
    """Safe to expose in diagnostics: credentials are deliberately excluded."""
    provider=os.getenv('FINN_AI_PROVIDER','gemini').strip().lower()
    if provider=='gemini':
        model=os.getenv('FINN_GEMINI_MODEL','').strip() or 'gemini-3.8-flash'
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

    def _request(self,model,payload,timeout):
        # Retry explicit server failures only. Quota/auth errors and ambiguous
        # transport failures do not trigger more requests or another provider.
        deadline=time.monotonic()+timeout
        for attempt in range(1,4):
            remaining=max(0.01,deadline-time.monotonic())
            response=httpx.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                                headers={'x-goog-api-key':os.environ['GEMINI_API_KEY'].strip()},
                                json=payload,timeout=httpx.Timeout(remaining,connect=min(10,remaining)),follow_redirects=False)
            if response.status_code not in (500,502,503,504) or attempt==3:
                return response,attempt
            delay=2**(attempt-1)+random.uniform(0,0.25)
            # Honor a numeric Retry-After, without sleeping beyond this call's
            # budget. Long waits return the error for an explicit later retry.
            retry_after=response.headers.get('retry-after','')
            if retry_after.isdigit():delay=max(delay,int(retry_after))
            if delay>8 or time.monotonic()+delay+1>=deadline:return response,attempt
            response.close()
            time.sleep(delay)

    def create(self,*,model,instructions,input,text,max_output_tokens,timeout=45,**_):
        if not re.fullmatch(r'gemini-[A-Za-z0-9_.-]+',model):
            raise ValueError('Invalid Gemini model.')
        config={'responseMimeType':'application/json','maxOutputTokens':max(8192,max_output_tokens)}
        schema=text['format'].get('schema')
        if schema:config['responseJsonSchema']=schema
        if model.startswith(('gemini-3','gemini-4')):
            config['thinkingConfig']={'thinkingLevel':'LOW'}
        payload={'systemInstruction':{'parts':[{'text':instructions}]},
                 'contents':[{'role':'user','parts':[{'text':input}]}],
                 'generationConfig':config}
        # No key in the URL, redirects, tools, or search grounding.
        response,attempts=self._request(model,payload,timeout)
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


def client_for(config):
    if config['provider']=='gemini':return GeminiClient()
    if config['provider']=='openai':
        from openai import OpenAI
        return OpenAI(api_key=os.environ['OPENAI_API_KEY'],timeout=45,max_retries=0)
    raise ValueError('Unsupported model provider.')
