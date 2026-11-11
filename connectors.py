"""Network adapters. Failures remain visible; unavailable data is never simulated."""
from datetime import datetime, timezone, timedelta
import hashlib
import ipaddress
import json
import socket
import re
import math
import os
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup
from store import ROOT,db,rows,now,ticker,import_pdf,settings,change

HEADERS={'User-Agent':'Mozilla/5.0 (compatible; FINN research prototype)'}

def public_url(url):
    parsed=urlparse(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError('Use a public HTTPS document URL.')
    addresses=socket.getaddrinfo(parsed.hostname,443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('Private and local network addresses are not allowed.')
    return url

def download(url,max_bytes=25*1024*1024):
    for _ in range(4):
        public_url(url)
        with requests.get(url,headers=HEADERS,timeout=(5,20),allow_redirects=False,stream=True) as r:
            if r.status_code in (301,302,303,307,308):
                url=urljoin(url,r.headers['Location']); continue
            r.raise_for_status()
            data=bytearray()
            for chunk in r.iter_content(65536):
                data.extend(chunk)
                if len(data)>max_bytes: raise ValueError('Download exceeds the size limit.')
            return bytes(data),url
    raise ValueError('Too many redirects.')

def discover(symbol):
    symbol=ticker(symbol)
    data,url=download(f'https://www.screener.in/company/{symbol}/consolidated/',3*1024*1024)
    return parse_discovery(data,url,symbol)

def parse_discovery(data,url,symbol):
    soup=BeautifulSoup(data,'html.parser')
    candidates=[]
    for section,kind in [('annual-reports','annual_report'),('concalls','transcript')]:
        area=soup.find(class_=section) or soup.find(id=section)
        if area is None:
            heading=next((h for h in soup.find_all(['h3','h2']) if ('annual report' if kind=='annual_report' else 'concall') in h.get_text().lower()),None)
            area=heading.parent if heading else None
        if area:
            for a in area.find_all('a',href=True):
                label=a.get_text(' ',strip=True)
                if kind=='transcript' and 'transcript' not in label.lower(): continue
                if kind=='annual_report' and not re.search(r'20\d{2}',label): continue
                link=urljoin(url,a['href'])
                if urlparse(link).scheme=='https':
                    parent=a.find_parent('li')
                    context=parent.get_text(' ',strip=True) if parent else label
                    heading=soup.find('h1')
                    candidates.append({'title':f'{symbol} · {label}', 'url':link,'kind':kind,
                        'period':'','discovery_label':context[:200], 'discovery_url':url,
                        'company_name':heading.get_text(' ',strip=True) if heading else symbol,
                        'notice':'Check company, document type and reporting period in the PDF before importing.'})
    # Return links for review; user-selected documents are imported with provenance.
    seen=set(); unique=[]
    for item in candidates:
        if item['url'] not in seen:
            seen.add(item['url']); unique.append(item)
    # Keep recent calls visible even when the annual-report section is long.
    return [d for kind in ('annual_report','transcript') for d in [x for x in unique if x['kind']==kind][:8]]

def classify(text):
    text=text.lower()
    for words,category,priority in [(['financial result','quarterly result'],'Results',90),(['appointment','resignation','management'],'Management',85),(['acquisition','merger','amalgamation'],'M&A',90),(['litigation','penalty','order from'],'Litigation',75),(['capacity','capital expenditure'],'Capex',75)]:
        if any(w in text for w in words): return category,priority
    return 'Routine',20

def refresh_filings(days=7):
    if days not in (1,7,30,365): raise ValueError('Unsupported time window.')
    try:return _refresh_nse_filings(days)
    except Exception as exc:
        from diagnostics import failure
        nse_error=failure(exc)
    result=refresh_company_filings(days)
    result['source_failures'].insert(0,{'source':'NSE',**nse_error})
    if not result['covered_tickers']:result['failed']=result['source_failures']
    return result

def _refresh_nse_filings(days=7):
    if days not in (1,7,30,365): raise ValueError('Unsupported time window.')
    portfolio={r['ticker'] for r in rows('SELECT ticker FROM companies WHERE portfolio=1')}
    session=requests.Session(); session.headers.update(HEADERS)
    session.get('https://www.nseindia.com',timeout=(5,15)).raise_for_status()
    from zoneinfo import ZoneInfo
    end=datetime.now(ZoneInfo('Asia/Kolkata')); start=end-timedelta(days=days)
    response=session.get('https://www.nseindia.com/api/corporate-announcements',params={'index':'equities','from_date':start.strftime('%d-%m-%Y'),'to_date':end.strftime('%d-%m-%Y')},timeout=(5,20))
    response.raise_for_status(); data=response.json()
    if not isinstance(data,list): raise ValueError('NSE returned an unexpected response.')
    added,ids=ingest_filings(data,portfolio)
    return {'added':added,'event_ids':ids,'source':'NSE','fetched_at':now(),
            'requested_start':start.isoformat(),'requested_end':end.isoformat(),
            'coverage_notice':'NSE response for requested dates; exchange completeness is not independently verified.'}

def parse_company_announcements(data,base_url):
    """Only PDF links with an unambiguous adjacent publication date are admitted."""
    soup=BeautifulSoup(data,'html.parser');result=[];seen=set()
    date_pattern=r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},\s*20\d{2}\b'
    for anchor in soup.find_all('a',href=True):
        url=urljoin(base_url,anchor['href'])
        if not url.startswith('https://') or not re.search(r'\.pdf(?:$|[?#])',url,re.I) or url in seen:continue
        area=anchor
        for _ in range(4):
            if area is None:break
            text=area.get_text(' ',strip=True);leading_date=re.match(date_pattern,text,re.I)
            pdf_links=[a for a in area.find_all('a',href=True) if re.search(r'\.pdf(?:$|[?#])',a['href'],re.I)]
            if len(text)<=1800 and leading_date and len(pdf_links)<=1:
                raw=leading_date.group();published=None
                for fmt in ('%b %d, %Y','%B %d, %Y'):
                    try:published=datetime.strptime(re.sub(r',\s*',', ',raw),fmt).date().isoformat();break
                    except ValueError:pass
                title=text[leading_date.end():].strip(' ·–-\n')
                if published and len(title)>=10:
                    seen.add(url);result.append({'title':title[:1000],'url':url,'publication_date':published});break
            area=area.parent
    return result

def refresh_company_filings(days=7):
    from zoneinfo import ZoneInfo
    from diagnostics import failure
    config_path=os.getenv('FINN_ANNOUNCEMENT_SOURCES',str(ROOT/'examples'/'announcement_sources.json'))
    with open(config_path) as source_file:sources=json.load(source_file)['sources']
    if not isinstance(sources,list) or len(sources)>20:raise ValueError('Configure at most 20 company announcement sources.')
    portfolio={r['ticker'] for r in rows('SELECT ticker FROM companies WHERE portfolio=1')}
    end=datetime.now(ZoneInfo('Asia/Kolkata'));start=end-timedelta(days=days)
    result={'source':'Company IR fallback','added':0,'event_ids':[],'covered_tickers':[],'source_failures':[],'partial':True,
        'requested_start':start.isoformat(),'requested_end':end.isoformat(),'fetched_at':now(),
        'coverage_notice':'Partial portfolio coverage: recent visible company-page PDFs only. Publication times are unknown for date-only entries; exchange/window completeness is not established.'}
    for source in sources:
        symbol=ticker(source['ticker'])
        if symbol not in portfolio:continue
        try:
            data,url=download(source['url'],3*1024*1024)
            candidates=parse_company_announcements(data,url)
            if not candidates:raise ValueError('No dated PDF announcements could be verified on company page.')
            result['covered_tickers'].append(symbol)
            with db() as c:
                for item in candidates:
                    day=datetime.fromisoformat(item['publication_date']).replace(tzinfo=end.tzinfo)
                    # Include overlapping days; never invent a publication hour.
                    if day>end or day+timedelta(days=1)<=start:continue
                    eid=hashlib.sha256((symbol+item['url']+item['publication_date']).encode()).hexdigest()[:24]
                    category,priority=classify(item['title'])
                    added=c.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?,?,?,?,?,0,0)',(eid,symbol,item['title'],category,day.isoformat(),priority,item['title'],None,item['url'],0)).rowcount
                    c.execute('INSERT OR IGNORE INTO event_metadata VALUES (?,?,?,?)',(eid,'Company IR','date',now()))
                    result['added']+=added;result['event_ids'].append(eid)
        except Exception as exc:result['source_failures'].append({'source':'Company IR','ticker':symbol,**failure(exc)})
    result['portfolio_count']=len(portfolio)
    if not result['covered_tickers']:result['partial']=False
    return result

def ingest_filings(data,portfolio):
    added=0; ids=[]
    with db() as c:
        for item in data:
            symbol=item.get('symbol','')
            if symbol not in portfolio: continue
            title=item.get('desc') or item.get('attchmntText') or 'Company announcement'
            detail=item.get('attchmntText') or title
            category,priority=classify(title+' '+detail)
            raw_date=item.get('an_dt') or item.get('sort_date') or ''
            date=None
            for fmt in ('%d-%b-%Y %H:%M:%S','%Y-%m-%d %H:%M:%S','%d-%m-%Y %H:%M:%S'):
                try: date=datetime.strptime(raw_date,fmt).isoformat()+'+05:30'; break
                except ValueError: pass
            if not date: continue  # Never substitute fetch time for publication time.
            url=item.get('attchmntFile') or ''
            if not url.startswith('https://'): url=''
            eid=hashlib.sha256((symbol+title+raw_date+url).encode()).hexdigest()[:24]
            result=c.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?,?,?,?,?,0,0)',(eid,symbol,title,category,date,priority,detail,None,url,0))
            added+=result.rowcount
            ids.append(eid)
    return added,ids

def evaluate_prices(closes,volumes,dates,config):
    if len(closes)<22 or len(volumes)!=len(closes) or len(dates)!=len(closes):
        raise ValueError('Need at least 22 completed trading sessions.')
    if any(not math.isfinite(float(x)) or x<=0 for x in closes[-22:]) or any(not math.isfinite(float(x)) or x<0 for x in volumes[-21:]):
        raise ValueError('Invalid market observations.')
    mean=sum(volumes[-21:-1])/20
    move=change(closes[-1],closes[-2])
    ratio=round(volumes[-1]/mean,2) if mean>0 else None
    return {'close':round(closes[-1],2),'date':dates[-1],'change_pct':move,'volume_ratio':ratio,'price_alert':move is not None and abs(move)>=config['price_threshold'],'volume_alert':ratio is not None and ratio>=config['volume_threshold'],'fetched_at':now()}

def refresh_prices():
    import yfinance as yf
    import store
    from zoneinfo import ZoneInfo
    yf.set_tz_cache_location(str(store.DATA/'market_cache'))
    result={'updated':0,'updated_tickers':[],'failed':[]}
    local_now=datetime.now(ZoneInfo('Asia/Kolkata'))
    for row in rows('SELECT ticker FROM companies WHERE portfolio=1'):
        symbol=row['ticker']
        try:
            history=yf.Ticker(symbol+'.NS').history(period='3mo',auto_adjust=False,timeout=10)
            # Today can be partial; include it only after the exchange close.
            history=history[[completed_session(d,local_now) for d in history.index]]
            history=history.dropna(subset=['Close','Volume'])
            data=evaluate_prices(history.Close.tolist(),history.Volume.tolist(),[d.date().isoformat() for d in history.index],settings())
            data['source']='Yahoo Finance'
            splits=history['Stock Splits'].tail(21) if 'Stock Splits' in history else []
            data['corporate_action']=any(float(v)!=0 for v in splits)
            if data['corporate_action']:
                data['price_alert']=False; data['volume_alert']=False
                data['notice']='A split is present in the comparison window. Review adjusted prices and volume before treating this as an unusual move.'
            data['symbol_verified']=True
            with db() as c: c.execute('INSERT OR REPLACE INTO prices VALUES (?,?)',(symbol,json.dumps(data)))
            result['updated']+=1
            result['updated_tickers'].append(symbol)
        except Exception as exc:
            from diagnostics import failure
            result['failed'].append({'ticker':symbol,**failure(exc)})
            if len(result['failed'])>=3 and not result['updated']:
                result['notice']='Stopped after three source failures. Check connectivity.'; break
    return result

def completed_session(session,local_now):
    return session.date()<local_now.date() or (session.date()==local_now.date() and local_now.hour>=16)
