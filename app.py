from contextlib import asynccontextmanager
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
from dotenv import load_dotenv
import threading
import uuid
from typing import Literal
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI,UploadFile,File,Form,HTTPException,Request
from fastapi.responses import FileResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
load_dotenv(Path(__file__).resolve().parent / '.env', override=False)

import store
from store import db,rows,ticker,now
import seed
import connectors
import monitoring
import access
from diagnostics import failure
from ai_provider import configuration
from network import ContactImport,import_contacts
from research import research,reliance_metrics
from acquisition import acquire,acquire_and_research

pool=ThreadPoolExecutor(max_workers=2)
job_lock=threading.Lock()

@asynccontextmanager
async def lifespan(app):
    access.validate_configuration()
    store.init(); seed.seed()
    with db() as c:
        c.execute("UPDATE jobs SET status='failed',error='Server restarted. Please retry.' WHERE status IN ('pending','running')")
        c.execute("UPDATE refresh_runs SET status='interrupted',finished_at=?,error_code='restart',error='Server stopped before this refresh completed. Retry the source.' WHERE status='running'",(now(),))
    runner=monitoring.Monitor(); runner.start()
    try: yield
    finally: runner.stop()

app=FastAPI(title='FINN',lifespan=lifespan)
app.mount('/static',StaticFiles(directory=store.ROOT/'static'),name='static')

@app.middleware('http')
async def local_safety(request:Request,call_next):
    # Same-origin mutation guard for the local single-user prototype.
    response=access.denied(request)
    origin=request.headers.get('origin')
    if response is None:
        if request.method not in ('GET','HEAD','OPTIONS') and origin and origin!=str(request.base_url).rstrip('/'):
            response=JSONResponse({'detail':'Cross-origin writes are not allowed.'},403)
        else:response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    return response

@app.api_route('/healthz',methods=['GET','HEAD'])
def readiness():
    try:
        with db() as c:c.execute('SELECT version FROM schema_migrations LIMIT 1').fetchone()
    except Exception:return JSONResponse({'status':'unavailable'},503)
    return {'status':'ok'}

@app.exception_handler(ValueError)
async def value_error(request,exc): return JSONResponse({'detail':str(exc)},400)

@app.get('/')
def home(): return FileResponse(store.ROOT/'static'/'index.html')

@app.get('/api/overview')
def overview():
    import os
    companies=rows('SELECT * FROM companies ORDER BY name')
    for company in companies:
        company['documents']=rows('SELECT id,title,kind,period FROM documents WHERE ticker=?',(company['ticker'],))
        price=rows('SELECT data FROM prices WHERE ticker=?',(company['ticker'],))
        company['price']=json.loads(price[0]['data']) if price else None
    ai=configuration()
    return {'companies':companies,'settings':store.settings(),'contacts':seed.contacts(),'ai_enabled':ai['configured'],'ai_provider':ai['provider'],'ai_model':ai['model'],'archive_count':rows('SELECT count(*) n FROM events WHERE archive=1')[0]['n'],'source_status':monitoring.source_health(),
      'hosting_notice':('Free hosting demo: saved events, settings, uploads, newly acquired documents and alerts can reset when the service sleeps, restarts or redeploys. Bundled public documents restore automatically. Monitoring pauses while the service sleeps.' if os.getenv('FINN_EPHEMERAL_DEMO')=='1' else None),
      'document_limits_mb':store.PDF_LIMITS_MB,'unread_alerts':rows('SELECT count(*) n FROM alerts WHERE read=0')[0]['n'],
      'monitoring_notice':'Monitoring runs while this local backend is running. Announcements: every 15 minutes; completed-session prices: after 16:00 IST.'}

@app.get('/api/events')
def events(mode:Literal['archive','live']='live',days:int=1,category:str='',saved:bool=False):
    if days not in (1,7,30,365): raise ValueError('Unsupported time window.')
    items=rows('SELECT e.*,c.name,c.sector,m.source provider,COALESCE(m.published_precision,\'timestamp\') published_precision FROM events e JOIN companies c ON c.ticker=e.ticker LEFT JOIN event_metadata m ON m.event_id=e.id WHERE e.archive=? AND c.portfolio=1',(int(mode=='archive'),))
    end=max([datetime.fromisoformat(e['published']) for e in items],default=datetime.now(timezone.utc)) if mode=='archive' else datetime.now(timezone.utc)
    start=end-timedelta(days=days)
    config=store.settings()
    items=[e for e in items if event_in_window(e,start,end) and (not category or e['category']==category) and (not saved or e['saved'])]
    for e in items:
        e['contacts']=seed.contacts(e['ticker'])[:2]
        e['alert']=e['category'] in config['categories']
    return {'items':sorted(items,key=lambda e:(e['priority'],e['published']),reverse=True),'window_end':end.isoformat(),'mode':mode,'source_health':monitoring.source_health()['filings']}

@app.get('/api/events/{event_id}')
def event(event_id:str):
    found=rows('SELECT e.*,c.name,c.sector,m.source provider,COALESCE(m.published_precision,\'timestamp\') published_precision FROM events e JOIN companies c ON c.ticker=e.ticker LEFT JOIN event_metadata m ON m.event_id=e.id WHERE e.id=?',(event_id,))
    if not found: raise HTTPException(404,'Event not found.')
    e=found[0]; e['contacts']=seed.contacts(e['ticker'])[:3]
    e['metrics']=reliance_metrics(e['document_id']) if e['ticker']=='RELIANCE' else []
    e['evidence']=rows('SELECT page,text FROM chunks WHERE document_id=? AND page<=3 ORDER BY page,id LIMIT 5',(e['document_id'],)) if e['document_id'] else []
    return e

def event_in_window(event,start,end):
    published=datetime.fromisoformat(event['published'])
    if event.get('published_precision')=='date':return published<=end and published+timedelta(days=1)>start
    return start<=published<=end

class EventState(BaseModel):
    saved:bool|None=None
    read:bool|None=None

@app.patch('/api/events/{event_id}')
def update_event(event_id:str,body:EventState):
    if not rows('SELECT id FROM events WHERE id=?',(event_id,)): raise HTTPException(404,'Event not found.')
    with db() as c:
        for key,value in body.model_dump(exclude_none=True).items(): c.execute(f'UPDATE events SET {key}=? WHERE id=?',(int(value),event_id))
    return {'ok':True}

@app.get('/api/network')
def network(q:str='',symbol:str=''): return seed.contacts(ticker(symbol) if symbol else '',q)

@app.post('/api/network/import')
def network_import(body:ContactImport): return import_contacts(body)

class Settings(BaseModel):
    price_threshold:float=Field(ge=0.1,le=100)
    volume_threshold:float=Field(ge=1,le=100)
    categories:list[Literal['Results','Management','M&A','Capex','Litigation','Routine']]
    monitoring_enabled:bool=True

@app.put('/api/settings')
def update_settings(body:Settings):
    with db() as c:
        for key,value in body.model_dump().items(): c.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(key,json.dumps(value)))
    return store.settings()

class Company(BaseModel):
    ticker:str
    name:str=Field(default='',max_length=100)

@app.post('/api/portfolio')
def add_company(body:Company):
    symbol=ticker(body.ticker)
    if symbol=='TATAMOTORS': raise ValueError('TATAMOTORS is historical. Follow TMPV (passenger vehicles) or TMCV (commercial vehicles) separately.')
    with db() as c:
        c.execute('INSERT INTO companies VALUES (?,?,?,1) ON CONFLICT(ticker) DO UPDATE SET portfolio=1',(symbol,body.name or symbol,'Unclassified'))
    return {'ticker':symbol}

@app.delete('/api/portfolio/{symbol}')
def remove_company(symbol:str):
    with db() as c: c.execute('UPDATE companies SET portfolio=0 WHERE ticker=?',(ticker(symbol),))
    return {'ok':True}

def submit(function,*args,report_progress=False):
    with job_lock:
        if rows("SELECT count(*) n FROM jobs WHERE status IN ('pending','running')")[0]['n']>=4:
            raise HTTPException(429,'Four jobs are already queued. Please wait for one to finish.')
        job_id=uuid.uuid4().hex
        with db() as c: c.execute('INSERT INTO jobs VALUES (?,?,?,?,?)',(job_id,'pending',None,None,now()))
    def work():
        with db() as c: c.execute("UPDATE jobs SET status='running' WHERE id=?",(job_id,))
        try:
            def progress(stage,message):
                with db() as c:c.execute("UPDATE jobs SET result=? WHERE id=? AND status='running'",(json.dumps({'stage':stage,'message':message}),job_id))
            result=function(*args,progress=progress) if report_progress else function(*args)
            with db() as c: c.execute("UPDATE jobs SET status='completed',result=? WHERE id=?",(json.dumps(result),job_id))
        except Exception as exc:
            # Do not expose provider URLs, keys, or exception internals to the client.
            message=str(exc) if isinstance(exc,ValueError) else failure(exc)['message']
            with db() as c: c.execute("UPDATE jobs SET status='failed',error=? WHERE id=?",(message,job_id))
    pool.submit(work)
    return {'job_id':job_id}

@app.get('/api/jobs/{job_id}')
def job(job_id:str):
    found=rows('SELECT * FROM jobs WHERE id=?',(job_id,))
    if not found: raise HTTPException(404,'Job not found.')
    result=found[0]; result['result']=json.loads(result['result']) if result['result'] else None
    return result

class ResearchRequest(BaseModel):
    ticker:str
    question:str=Field(min_length=3,max_length=1500)
    document_id:str|None=None
    periods:list[str]=Field(default_factory=list,max_length=8)
    auto_acquire:bool=True

@app.post('/api/research')
def ask(body:ResearchRequest):
    symbol=ticker(body.ticker)
    if body.document_id and not rows('SELECT id FROM documents WHERE id=? AND ticker=?',(body.document_id,symbol)):
        raise HTTPException(404,'Document not found for this company.')
    return submit(acquire_and_research,symbol,body.question,body.document_id,body.periods,body.auto_acquire,report_progress=True)

class AcquireRequest(BaseModel):
    ticker:str
    force:bool=False

@app.post('/api/documents/acquire')
def acquire_documents(body:AcquireRequest):
    return submit(acquire,ticker(body.ticker),body.force,report_progress=True)

@app.post('/api/refresh/{kind}')
def refresh(kind:Literal['filings','prices'],days:int=7):
    if days not in (1,7,30,365): raise ValueError('Unsupported time window.')
    return submit(monitoring.run_refresh,kind,days)

@app.get('/api/alerts')
def alerts():
    config=store.settings(); result=[]
    for r in rows('SELECT p.* FROM prices p JOIN companies c ON c.ticker=p.ticker WHERE c.portfolio=1'):
        p=json.loads(r['data'])
        if not p.get('corporate_action') and ((p['change_pct'] is not None and abs(p['change_pct'])>=config['price_threshold']) or (p['volume_ratio'] is not None and p['volume_ratio']>=config['volume_threshold'])): result.append({'ticker':r['ticker'],**p})
    return result

@app.get('/api/notifications')
def notifications():
    items=rows('SELECT * FROM alerts ORDER BY created_at DESC LIMIT 100')
    for item in items: item['contacts']=seed.contacts(item['ticker'])[:2]
    return {'items':items,'unread':rows('SELECT count(*) n FROM alerts WHERE read=0')[0]['n']}

class ReadState(BaseModel): read:bool=True

@app.patch('/api/notifications/{alert_id}')
def read_notification(alert_id:str,body:ReadState):
    with db() as c:
        if not c.execute('UPDATE alerts SET read=? WHERE id=?',(int(body.read),alert_id)).rowcount: raise HTTPException(404,'Alert not found.')
    return {'ok':True}

@app.get('/api/health')
def health(): return {'status':'ok','sources':monitoring.source_health(),'monitoring_enabled':store.settings()['monitoring_enabled']}

@app.get('/api/coverage/{symbol}')
def document_coverage(symbol:str): return store.coverage(ticker(symbol))

@app.get('/api/documents')
def documents(symbol:str): return rows('SELECT id,title,kind,period,source_url FROM documents WHERE ticker=?',(ticker(symbol),))

@app.get('/api/documents/{document_id}/file')
def document_file(document_id:str):
    found=rows('SELECT path FROM documents WHERE id=?',(document_id,))
    if not found: raise HTTPException(404,'Document not found.')
    return FileResponse(found[0]['path'],media_type='application/pdf')

@app.post('/api/documents/upload')
def upload(file:UploadFile=File(...),symbol:str=Form(...),kind:Literal['filing','annual_report','transcript']=Form(...),period:str=Form(''),title:str=Form(''),event_id:str=Form(''),identity_confirmed:bool=Form(False)):
    if not identity_confirmed: raise ValueError('Confirm the company, document type and reporting period in the PDF before importing.')
    content=file.file.read(store.pdf_limit(kind)+1)
    if event_id: validate_event_import(event_id,ticker(symbol),kind)
    doc_id=store.import_pdf(content,symbol,title[:200] or file.filename,kind,period[:100],verification='user_confirmed')
    if event_id:
        with db() as c: c.execute('UPDATE events SET document_id=? WHERE id=?',(doc_id,event_id))
    return {'document_id':doc_id}

class Discover(BaseModel): ticker:str
@app.post('/api/documents/discover')
def discover(body:Discover): return submit(connectors.discover,ticker(body.ticker))

class ImportURL(BaseModel):
    ticker:str
    url:str=Field(max_length=2000)
    title:str=Field(max_length=200)
    kind:Literal['annual_report','transcript','filing']
    period:str=Field(default='',max_length=100)
    discovery_url:str=Field(default='',max_length=2000)
    identity_confirmed:bool=False
    event_id:str|None=None

@app.post('/api/documents/import')
def import_url(body:ImportURL):
    symbol=ticker(body.ticker)
    if not body.identity_confirmed: raise ValueError('Open the PDF and confirm the company, document type and reporting period before import.')
    if body.event_id: validate_event_import(body.event_id,symbol,body.kind)
    def work():
        content,url=connectors.download(body.url,max_bytes=store.pdf_limit(body.kind))
        doc_id=store.import_pdf(content,symbol,body.title,body.kind,body.period,url,body.discovery_url,verification='user_confirmed')
        if body.event_id:
            with db() as c: c.execute('UPDATE events SET document_id=? WHERE id=?',(doc_id,body.event_id))
        return {'document_id':doc_id}
    return submit(work)

def validate_event_import(event_id,symbol,kind):
    if kind!='filing' or not rows('SELECT id FROM events WHERE id=? AND ticker=?',(event_id,symbol)):
        raise ValueError('A filing can only be attached to an event for the same company.')
