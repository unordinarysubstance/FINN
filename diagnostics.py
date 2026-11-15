"""Allowlisted diagnostics with redacted structured provider errors."""
import json
import socket
import os
import re


def _classification(exc):
    name=type(exc).__name__
    status=getattr(exc,'status_code',None)
    response=getattr(exc,'response',None)
    if status is None and response is not None: status=getattr(response,'status_code',None)
    body=getattr(exc,'body',None)
    code=body.get('code') if isinstance(body,dict) else None
    if isinstance(body,dict) and isinstance(body.get('error'),dict): code=body['error'].get('code',code)
    if code in ('insufficient_quota','billing_hard_limit_reached'):
        return {'code':'quota','message':'The model account has no available API quota. Check billing.'}
    if status==401 or name=='AuthenticationError':
        return {'code':'authentication','message':'The provider rejected authentication. Check the server-side API key.'}
    if status in (403,404) or name in ('PermissionDeniedError','NotFoundError'):
        return {'code':'access','message':'The source or configured model denied access or was not found.'}
    if status==429:
        return {'code':'rate_limit','message':'The provider rate limit was reached. Retry later.'}
    if status==400:
        return {'code':'invalid_request','message':'The provider rejected the request format, parameters, or model configuration.'}
    if status in (500,502,503,504):
        return {'code':'temporarily_unavailable','message':'The model provider is temporarily unavailable or overloaded. Please retry later.'}
    if 'Timeout' in name:
        return {'code':'timeout','message':'The provider timed out. Retry later.'}
    if isinstance(exc,socket.gaierror) or any(s in name for s in ('Connection','Connect','DNS')):
        return {'code':'connectivity','message':'Connection failed. Check DNS, network access, and sandbox restrictions.'}
    if isinstance(exc,PermissionError):
        return {'code':'permission','message':'This environment denied the network or filesystem operation.'}
    if isinstance(exc,(ValueError,TypeError,KeyError,json.JSONDecodeError)):
        return {'code':'validation','message':'The response failed validation. Existing evidence remains available.'}
    return {'code':'provider','message':'The source could not be reached or processed. Existing data was preserved.'}


def safe_provider_message(value):
    """Redact credentials and URLs from the provider's structured error message."""
    text=str(value)
    for name,value in os.environ.items():
        if value and len(value)>=6 and any(part in name.upper() for part in ('KEY','TOKEN','SECRET','PASSWORD')):
            text=text.replace(value,'[redacted]')
    text=re.sub(r'(?i)\b(?:sk|sess)-[A-Za-z0-9_-]+','[redacted]',text)
    text=re.sub(r'\bAIza[A-Za-z0-9_-]+','[redacted]',text)
    text=re.sub(r'(?i)bearer\s+\S+','Bearer [redacted]',text)
    text=re.sub(r'https?://\S+','[URL removed]',text)
    return ' '.join(text.split())[:600]


def failure(exc):
    result=_classification(exc)
    result['exception_type']=type(exc).__name__
    status=getattr(exc,'status_code',None)
    if status is None: status=getattr(getattr(exc,'response',None),'status_code',None)
    if type(status) is int: result['http_status']=status
    attempts=getattr(exc,'attempts',None)
    if type(attempts) is int:result['attempts']=attempts
    body=getattr(exc,'body',None)
    if isinstance(body,dict):
        error=body.get('error',body)
        if isinstance(error,dict):
            for key in ('code','type','param','status'):
                value=error.get(key)
                if isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_.\[\]-]{1,100}',value):result['provider_'+key]=safe_provider_message(value)
            if isinstance(error.get('message'),str):result['provider_message']=safe_provider_message(error['message'])
    # Only known local validation strings are safe to display verbatim.
    known=('Company identity requires manual inspection.','Document type requires manual inspection.',
           'No verified reporting period in manifest.','Reporting year requires manual inspection.',
           'Download exceeds the size limit.','Local PDF exceeds the size limit.',
           'Supply a PDF smaller than 25 MB.','Supply a valid PDF.','Annual reports must be no larger than 100 MB.',
           'Filings and transcripts must be no larger than 25 MB.','PDF exceeds 1,000 pages.',
           'No readable text found. This PDF needs OCR before import.')
    if isinstance(exc,ValueError) and str(exc) in known:result['message']=str(exc)
    return result
