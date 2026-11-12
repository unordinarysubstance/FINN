"""Official recent NSE RSS fallback; never claim historical/window completeness."""
from datetime import datetime,timedelta,timezone
from email.utils import parsedate_to_datetime
import hashlib
import re
from urllib.parse import urlparse,parse_qs,unquote
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
import connectors
import store

RSS_URL='https://nsearchives.nseindia.com/content/RSS/Online_announcements.xml'

def company_key(value):
    value=re.sub(r'\b(?:limited|ltd)\b','',value.lower().replace('&',' and '))
    return re.sub(r'[^a-z0-9]','',value)

def publication(value):
    try:
        date=parsedate_to_datetime(value)
        if date:return date.replace(tzinfo=ZoneInfo('Asia/Kolkata')) if date.tzinfo is None else date
    except (ValueError,TypeError,OverflowError):pass
    for fmt in ('%d-%b-%Y %H:%M:%S','%d-%m-%Y %H:%M:%S','%Y-%m-%d %H:%M:%S'):
        try:return datetime.strptime(value,fmt).replace(tzinfo=ZoneInfo('Asia/Kolkata'))
        except ValueError:pass
    try:
        date=datetime.fromisoformat(value)
        if date.tzinfo:return date
    except ValueError:pass
    return None

def parse_feed(data,companies):
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ValueError('RSS declarations are not supported.')
    root=ET.fromstring(data)
    if root.tag!='rss' or root.find('channel') is None:raise ValueError('The exchange did not return an RSS channel.')
    result=[];dates=[]
    for item in root.findall('./channel/item'):
        title=item.findtext('title') or '';link=(item.findtext('link') or '').strip()
        text=BeautifulSoup(item.findtext('description') or '','html.parser').get_text(' ',strip=True)
        raw_date=item.findtext('pubDate') or '';date=publication(raw_date)
        if date is None:continue
        dates.append(date)
        symbol=(item.findtext('symbol') or '').strip().upper()
        if symbol not in companies:
            quoted=parse_qs(urlparse(link).query).get('symbol',[''])[0]
            if quoted in companies:symbol=quoted
            else:
                matches=[s for s,c in companies.items() if company_key(title)==company_key(c['name']) or re.search(r'(?:^|/)'+re.escape(s)+r'[_-]',unquote(urlparse(link).path),re.I)]
                if len(matches)!=1:continue
                symbol=matches[0]
        host=(urlparse(link).hostname or '').removeprefix('www.')
        if urlparse(link).scheme!='https' or not (host=='nseindia.com' or host.endswith('.nseindia.com')):continue
        result.append({'ticker':symbol,'title':(text or title)[:180],'summary':text or title,'url':link,'published':date.isoformat()})
    if not dates:raise ValueError('No dated RSS items were available.')
    return result,min(dates),max(dates)

def refresh_nse_rss(days=7):
    if days not in (1,7,30,365):raise ValueError('Unsupported time window.')
    companies={c['ticker']:c for c in store.rows('SELECT ticker,name FROM companies WHERE portfolio=1')}
    # Reuse the official identity cache when available, without requiring another network request.
    catalog=store.rows("SELECT result FROM cache WHERE key='nse-directory-v1'")
    if catalog:
        import json
        directory=json.loads(catalog[0]['result']).get('entries',{})
        for symbol,company in companies.items():company['name']=directory.get(symbol,{}).get('company_name',company['name'])
    raw,_=connectors.download(RSS_URL,5*1024*1024)
    items,oldest,newest=parse_feed(raw,companies)
    end=datetime.now(timezone.utc);start=end-timedelta(days=days);ids=[];added=0
    with store.db() as c:
        for item in items:
            date=datetime.fromisoformat(item['published'])
            if not start<=date<=end:continue
            category,priority=connectors.classify(item['title']+' '+item['summary'])
            existing=c.execute('SELECT id FROM events WHERE ticker=? AND source_url=? AND archive=0',(item['ticker'],item['url'])).fetchone()
            if existing:
                ids.append(existing['id']);continue
            eid=hashlib.sha256(('nse-rss:'+item['ticker']+item['url']+item['published']).encode()).hexdigest()[:24]
            added+=c.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?,?,?,?,?,0,0)',(eid,item['ticker'],item['title'][:1000],category,item['published'],priority,item['summary'][:4000],None,item['url'],0)).rowcount
            c.execute('INSERT OR IGNORE INTO event_metadata VALUES (?,?,?,?)',(eid,'NSE RSS','timestamp',store.now()))
            ids.append(eid)
    return {'source':'NSE RSS','partial':True,'added':added,'event_ids':ids,'source_failures':[],
            'covered_tickers':sorted({i['ticker'] for i in items}),'portfolio_count':len(companies),
            'requested_start':start.isoformat(),'requested_end':end.isoformat(),'fetched_at':store.now(),
            'observed_start':oldest.isoformat(),'observed_end':newest.isoformat(),
            'coverage_notice':'Recent official exchange RSS items across the portfolio. The feed is bounded; complete coverage of the selected historical window is not established.'}
