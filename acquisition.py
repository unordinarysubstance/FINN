"""On-demand primary-source acquisition for NSE companies, independent of demo seeds."""
import csv
import io
import json
import re
import threading
import time
import unicodedata
from datetime import datetime,timezone,timedelta
from urllib.parse import urljoin,urlparse
from bs4 import BeautifulSoup
from pypdf import PdfReader
import connectors
import store
from diagnostics import failure

DIRECTORY_URL='https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv'
_locks=[threading.Lock() for _ in range(32)]
_directory_lock=threading.Lock()
POLICY=1

class SourceValidation(ValueError):pass

def cached(key):
    result=store.rows('SELECT result FROM cache WHERE key=?',(key,))
    return json.loads(result[0]['result']) if result else None

def save(key,value):
    with store.db() as c:c.execute('INSERT OR REPLACE INTO cache VALUES (?,?)',(key,json.dumps(value)))

def recent(value,seconds):
    try:return datetime.now(timezone.utc)-datetime.fromisoformat(value['checked_at'])<timedelta(seconds=seconds)
    except (KeyError,TypeError,ValueError):return False

def directory_identity(symbol):
    """Use the official equity list when reachable; a directory outage is not an invalid ticker."""
    with _directory_lock:
        listing=cached('nse-directory-v1')
        if not recent(listing,86400):
            raw,_=connectors.download(DIRECTORY_URL,3*1024*1024)
            entries={}
            for row in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
                row={k.strip():str(v).strip() for k,v in row.items() if k}
                if row.get('SYMBOL') and row.get('NAME OF COMPANY'):entries[row['SYMBOL']]={'company_name':row['NAME OF COMPANY'],'isin':row.get('ISIN NUMBER','')}
            if not entries:raise SourceValidation('The NSE directory did not contain company records.')
            listing={'checked_at':store.now(),'entries':entries};save('nse-directory-v1',listing)
        return listing['entries'].get(symbol)

def normal(text):
    text=unicodedata.normalize('NFKC',text).lower().replace('&',' and ')
    return re.sub(r'[^a-z0-9]+','',re.sub(r'\b(?:limited|ltd)\b','limited',text))

def reporting_period(kind,pages):
    # Read reporting labels from cover pages, never listing dates or URL filenames.
    for page in pages[:8 if kind=='annual_report' else 3]:
        text=' '.join(unicodedata.normalize('NFKC',page).replace('–','-').replace('—','-').split())
        text=re.sub(r'\b2\s+0\s+(\d)\s+(\d)\b',r'20\1\2',text)
        text=re.sub(r'(20\d{2}\s*[-/]\s*)(\d)\s+(\d)\b',r'\1\2\3',text)
        if kind=='annual_report':
            patterns=[r'(?:annual|integrated)\s+(?:annual\s+)?report\D{0,60}(20\d{2})\s*[-/]\s*(\d{2,4})',
                      r'(?:financial\s+year|fiscal\s+year)\D{0,15}(20\d{2})\s*[-/]\s*(\d{2,4})']
            for pattern in patterns:
                m=re.search(pattern,text,re.I)
                if m:
                    start=int(m[1]);end=int(m[2]) if len(m[2])==4 else int(m[1][:2]+m[2])
                    if end==start+1:return 'FY'+str(end)
            m=re.search(r'(?:annual|integrated)\s+(?:annual\s+)?report\D{0,35}(?:FY\s*)?(20\d{2})(?!\s*[-/]\s*\d)',text,re.I)
            if m:return 'FY'+m[1]
        else:
            m=re.search(r'\bQ([1-4])\s+(20\d{2})\s*[-/]\s*(20\d{2}|\d{2})\b',text,re.I)
            if m:
                end=int(m[3]) if len(m[3])==4 else int(m[2][:2]+m[3])
                if end==int(m[2])+1:return 'Q'+m[1]+' FY'+str(end)
            m=re.search(r'\bQ([1-4])\s*(?:and|&)?\s*(?:H[12]\s*)?(?:FY|fiscal\s+year)\s*[\x27’]?(20\d{2}|\d{2})(?:\s*[-/]\s*(\d{2,4}))?\b',text,re.I)
            if m:
                year=m[3] or m[2];year=year if len(year)==4 else '20'+year
                return 'Q'+m[1]+' FY'+year
            # Some issuers use calendar years; preserve the literal reporting date.
            m=re.search(r'quarter\s+(?:and\s+(?:half\s+year|year)\s+)?ended\s+(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s*,?\s*20\d{2}|[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?\s*,?\s*20\d{2})',text,re.I)
            if m:return 'Quarter ended '+m[1]
    raise SourceValidation('The reporting period could not be verified on the PDF cover pages.')

def inspect_pdf(content,company,kind):
    if not content.startswith(b'%PDF-'):raise SourceValidation('The source did not return a PDF.')
    reader=PdfReader(io.BytesIO(content))
    if len(reader.pages)>1000:raise SourceValidation('PDF exceeds 1,000 pages.')
    pages=[p.extract_text() or '' for p in reader.pages[:8]]
    cover=normal(' '.join(pages));name=normal(company['company_name']);isin=company.get('isin','')
    words=[w for w in re.findall(r'[A-Za-z0-9]+',company['company_name']) if w.lower() not in ('limited','ltd','the','and')]
    core=normal(' '.join(words));acronym=''.join(w[0] for w in words)
    # Legal suffixes and a derived legal acronym account for ordinary issuer branding.
    identity_forms=[name]+([core] if len(core)>=6 else [])
    if len(acronym)>=3:identity_forms.append(normal(acronym+' Limited'))
    if not name or not (any(form in cover for form in identity_forms) or (isin and normal(isin) in cover)):
        raise SourceValidation('The PDF company identity did not match the requested NSE issuer.')
    text=' '.join(' '.join(pages).lower().split())
    if kind=='annual_report':
        if not re.search(r'(?:annual|integrated)\s+(?:annual\s+)?report',text):raise SourceValidation('The PDF was not identifiable as an annual report.')
    elif not ('transcript' in text or ('conference call' in text and len(text)>2500 and 'thank you' in text and re.search('question|operator|moderator',text))):
        raise SourceValidation('The PDF was not identifiable as an earnings-call transcript.')
    period=reporting_period(kind,pages)
    years=[int(y) for y in re.findall(r'20\d{2}',period)]
    if any(y>datetime.now().year+1 or y<1990 for y in years):raise SourceValidation('The PDF reporting year was outside the supported range.')
    return period

def issuer_links(data,base_url,website):
    """Only crawl the issuer's own site; extract PDF links, never secondary analysis."""
    host=(urlparse(website).hostname or '').removeprefix('www.')
    documents=[];pages=[]
    for a in BeautifulSoup(data,'html.parser').find_all('a',href=True):
        link=urljoin(base_url,a['href']);p=urlparse(link);label=a.get_text(' ',strip=True)
        own=(p.hostname or '').removeprefix('www.')==host or (p.hostname or '').endswith('.'+host)
        if p.scheme!='https' or not own:continue
        context=label+' '+p.path
        if re.search(r'\.pdf$',p.path,re.I):
            kind='transcript' if re.search('transcript',context,re.I) else 'annual_report' if re.search(r'annual.?report|integrated.?report',context,re.I) else None
            if kind:documents.append({'url':link,'title':label or p.path.split('/')[-1],'kind':kind,'discovery_url':base_url})
        elif re.search(r'investor|annual.?report|financial.?result|earning|concall|transcript',context,re.I):pages.append(link)
    return documents,list(dict.fromkeys(pages))

def primary_url(url,website):
    host=(urlparse(url).hostname or '').removeprefix('www.')
    issuer=(urlparse(website or '').hostname or '').removeprefix('www.')
    return urlparse(url).scheme=='https' and any(host==base or host.endswith('.'+base) for base in ('nseindia.com','bseindia.com',issuer) if base)

def acquire(symbol,force=False,progress=None):
    symbol=store.ticker(symbol);emit=progress or (lambda stage,message:None)
    with _locks[sum(symbol.encode())%len(_locks)]:
        coverage=store.coverage(symbol);key='acquisition-v'+str(POLICY)+':'+symbol
        if not force and not coverage['gaps']:return {'ticker':symbol,'status':'existing','documents':[],'failures':[],'coverage':coverage}
        previous=cached(key)
        if not force and recent(previous,600):return {**previous,'cached_attempt':True,'coverage':coverage}
        report={'ticker':symbol,'checked_at':store.now(),'status':'unavailable','documents':[],'failures':[],'notice':'Only verified annual reports and transcripts enter research. Discovery dates are not reporting periods.'}
        deadline=time.monotonic()+210
        try:
            emit('discovering','Finding annual reports and earnings-call transcripts for '+symbol+'…')
            profile=connectors.discover_profile(symbol)
            report['failures'].extend(profile.get('source_failures',[]))
            identity=None
            try:identity=directory_identity(symbol)
            except Exception as exc:report['directory_error']=failure(exc)
            if not identity and not (profile['exchange_link_verified'] or profile.get('quote_verified')):raise SourceValidation('The requested symbol could not be verified against the available NSE listing sources.')
            company=identity or {'company_name':profile['company_name'],'isin':''}
            if not company['company_name']:raise SourceValidation('No company identity was available for this ticker.')
            report['company_name']=company['company_name'];report['identity_source']='NSE equity directory' if identity else 'Screener listing with exact NSE quote link' if profile['exchange_link_verified'] else 'Yahoo NSE equity quote metadata'
            with store.db() as c:
                c.execute('INSERT INTO companies VALUES (?,?,?,0) ON CONFLICT(ticker) DO UPDATE SET name=excluded.name',(symbol,company['company_name'],'Unclassified'))
            seen=set();attempts=0
            def ingest(items):
                nonlocal attempts
                for item in items:
                    if time.monotonic()>deadline or attempts>=8:return
                    current=store.coverage(symbol)
                    if (item['kind']=='annual_report' and current['annual_reports']>=1) or (item['kind']=='transcript' and len({d['period'] for d in current['documents'] if d['kind']=='transcript' and d['period']})>=2):continue
                    if item['url'] in seen:continue
                    seen.add(item['url']);attempts+=1
                    try:
                        if not primary_url(item['url'],profile.get('website')):raise SourceValidation('Automatic imports accept only issuer or exchange document links.')
                        emit('downloading','Downloading '+symbol+' '+item['kind'].replace('_',' ')+'…')
                        content,url=connectors.download(item['url'],max_bytes=store.pdf_limit(item['kind']))
                        period=inspect_pdf(content,company,item['kind'])
                        if store.rows('SELECT id FROM documents WHERE ticker=? AND kind=? AND period=?',(symbol,item['kind'],period)):continue
                        emit('indexing','Indexing original PDF pages for '+symbol+' · '+period+'…')
                        doc=store.import_pdf(content,symbol,company['company_name']+' · '+period+' · '+item['kind'].replace('_',' '),item['kind'],period,url,item['discovery_url'],verification='automatic_content_checks')
                        report['documents'].append({'document_id':doc,'kind':item['kind'],'period':period,'url':url,'status':'indexed'})
                    except Exception as exc:report['failures'].append({'url':item['url'],'kind':item['kind'],**({'code':'source_validation','message':str(exc)} if isinstance(exc,SourceValidation) else failure(exc))})
            # Alternate document types so a blocked annual-report host does not consume the entire budget.
            docs=profile['documents'];ordered=[]
            for i in range(3):
                for kind in ('annual_report','transcript'):
                    group=[d for d in docs if d['kind']==kind]
                    if i<len(group):ordered.append(group[i])
            ingest(ordered)
            website=profile.get('website')
            if website and store.coverage(symbol)['gaps']:
                if website.startswith('http://'):website='https://'+website[7:]
                queue=[website];visited=set()
                while queue and len(visited)<4 and time.monotonic()<deadline and store.coverage(symbol)['gaps']:
                    page=queue.pop(0)
                    if page in visited:continue
                    visited.add(page)
                    try:
                        emit('discovering','Checking '+symbol+'’s investor-relations pages…')
                        data,actual=connectors.download(page,3*1024*1024)
                        items,links=issuer_links(data,actual,website);ingest(items);queue.extend(links[:8])
                    except Exception as exc:report['failures'].append({'url':page,**failure(exc)})
        except Exception as exc:report['failures'].append({'code':'source_validation','message':str(exc)} if isinstance(exc,SourceValidation) else failure(exc))
        report['coverage']=store.coverage(symbol)
        report['status']='ready' if not report['coverage']['gaps'] else 'partial' if report['coverage']['annual_reports'] or report['coverage']['transcripts'] else 'unavailable'
        save(key,report)
        return report

def acquire_and_research(symbol,question,document_id=None,periods=None,auto_acquire=True,progress=None):
    from research import research
    emit=progress or (lambda stage,message:None)
    acquisition=acquire(symbol,progress=emit) if auto_acquire and not document_id else None
    emit('analysing','Reading company sources and checking the research findings…')
    result=research(symbol,question,document_id,periods)
    if acquisition:
        result['acquisition']=acquisition
        if acquisition['status'] in ('partial','unavailable'):result['limitations'].append('Automatic source acquisition is '+acquisition['status']+'. Some reports or transcript periods could not be verified; inspect source coverage.')
    return result
