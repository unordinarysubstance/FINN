"""Local single-investor persistence. Documents and all citations retain provenance."""
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from contextlib import contextmanager, closing
from datetime import datetime, timezone
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent
DATA = Path(os.getenv('FINN_DATA_DIR', ROOT / 'data'))
logging.getLogger('pypdf').setLevel(logging.ERROR)

def now():
    return datetime.now(timezone.utc).isoformat()

def ticker(value):
    value = value.strip().upper().removesuffix('.NS')
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9&-]{0,29}', value):
        raise ValueError('Enter an NSE symbol such as TCS or RELIANCE.')
    return value

@contextmanager
def db():
    DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DATA / 'finn.sqlite3', timeout=30)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

def install_public_seed():
    """Install a generated public-document index only into a new workspace."""
    source=ROOT/'demo_data'/'public.sqlite3';target=DATA/'finn.sqlite3'
    if os.getenv('FINN_DISABLE_DEMO_SEED')=='1' or target.exists() or not source.exists():return
    DATA.mkdir(parents=True,exist_ok=True)
    handle,name=tempfile.mkstemp(prefix='.public-seed-',suffix='.sqlite3',dir=DATA);os.close(handle)
    temporary=Path(name)
    try:
        with closing(sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(temporary)) as dest:
            src.backup(dest)
            with dest:
                for doc_id,relative in dest.execute('SELECT id,path FROM documents').fetchall():
                    path=(ROOT/relative).resolve();parts=Path(relative).parts
                    if Path(relative).is_absolute() or not parts or parts[0] not in ('demo_documents','demo_primary') or path.suffix.lower()!='.pdf' or not path.is_relative_to(ROOT.resolve()) or not path.is_file():
                        raise ValueError('Invalid public corpus file path.')
                    dest.execute('UPDATE documents SET path=? WHERE id=?',(str(path),doc_id))
        # Atomic creation: never replace an existing investor database.
        try:os.link(temporary,target)
        except FileExistsError:pass
    finally:temporary.unlink(missing_ok=True)

def init(seed_demo=True):
    if seed_demo:install_public_seed()
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS companies(ticker TEXT PRIMARY KEY, name TEXT, sector TEXT, portfolio INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY, ticker TEXT, title TEXT, kind TEXT, period TEXT, source_url TEXT, path TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY, document_id TEXT REFERENCES documents(id), page INTEGER, text TEXT);
        CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(text, content='chunks', content_rowid='id');
        CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, ticker TEXT, title TEXT, category TEXT, published TEXT, priority INTEGER, summary TEXT, document_id TEXT, source_url TEXT, archive INTEGER DEFAULT 0, read INTEGER DEFAULT 0, saved INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS contacts(id TEXT PRIMARY KEY, data TEXT);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS prices(ticker TEXT PRIMARY KEY, data TEXT);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, status TEXT, result TEXT, error TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, result TEXT);
        CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT);
        CREATE TABLE IF NOT EXISTS document_metadata(document_id TEXT PRIMARY KEY REFERENCES documents(id), discovery_url TEXT DEFAULT '', published_at TEXT, verification TEXT DEFAULT 'user_supplied');
        CREATE TABLE IF NOT EXISTS alerts(id TEXT PRIMARY KEY, ticker TEXT, kind TEXT, identity TEXT UNIQUE, title TEXT, reason TEXT, observed_at TEXT, created_at TEXT, event_id TEXT, read INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS refresh_runs(id TEXT PRIMARY KEY, source TEXT, started_at TEXT, finished_at TEXT, status TEXT, window_start TEXT, window_end TEXT, result TEXT, error_code TEXT, error TEXT);
        CREATE TABLE IF NOT EXISTS monitor_state(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS event_metadata(event_id TEXT PRIMARY KEY REFERENCES events(id), source TEXT, published_precision TEXT, fetched_at TEXT);
        CREATE INDEX IF NOT EXISTS chunks_document_page ON chunks(document_id,page);
        CREATE INDEX IF NOT EXISTS events_published ON events(archive,published);
        ''')
        c.execute('INSERT OR IGNORE INTO schema_migrations VALUES (1,?)',(now(),))
        c.execute('INSERT OR IGNORE INTO schema_migrations VALUES (3,?)',(now(),))
        if not c.execute('SELECT 1 FROM schema_migrations WHERE version=2').fetchone():
            old=c.execute("SELECT portfolio FROM companies WHERE ticker='TATAMOTORS'").fetchone()
            if old:
                c.execute("INSERT OR IGNORE INTO companies VALUES ('TMPV','Tata Motors Passenger Vehicles','Automotive',?)",(old['portfolio'],))
                c.execute("UPDATE companies SET portfolio=0 WHERE ticker='TATAMOTORS'")
            # Preserve every historical document, contact and saved event under its original symbol.
            c.execute('INSERT INTO schema_migrations VALUES (2,?)',(now(),))
        for key, value in {'price_threshold':5.0,'volume_threshold':2.0,'categories':['Results','Management','M&A','Capex','Litigation'],'monitoring_enabled':True}.items():
            c.execute('INSERT OR IGNORE INTO settings VALUES (?,?)',(key,json.dumps(value)))

def rows(sql, params=()):
    with db() as c:
        return [dict(r) for r in c.execute(sql,params).fetchall()]

def settings():
    return {r['key']:json.loads(r['value']) for r in rows('SELECT * FROM settings')}

PDF_LIMITS_MB={'annual_report':100,'transcript':25,'filing':25}

def pdf_limit(kind):
    if kind not in PDF_LIMITS_MB: raise ValueError('Unsupported document type.')
    return PDF_LIMITS_MB[kind]*1024*1024

def import_pdf(content, symbol, title, kind='filing', period='', source_url='', discovery_url='', published_at=None, verification='user_supplied'):
    symbol=ticker(symbol)
    if kind not in ('filing','annual_report','transcript'):
        raise ValueError('Unsupported document type.')
    if len(content)>pdf_limit(kind):
        raise ValueError('Annual reports must be no larger than 100 MB.' if kind=='annual_report' else 'Filings and transcripts must be no larger than 25 MB.')
    if not content.startswith(b'%PDF-'): raise ValueError('Supply a valid PDF.')
    doc_id=hashlib.sha256(symbol.encode()+kind.encode()+content).hexdigest()[:24]
    if rows('SELECT id FROM documents WHERE id=?',(doc_id,)):
        return doc_id
    reader=PdfReader(io.BytesIO(content))
    if len(reader.pages)>1000:
        raise ValueError('PDF exceeds 1,000 pages.')
    chunks=[]
    for number,page in enumerate(reader.pages,1):
        text=page.extract_text() or ''
        # Keep page boundaries and overlapping windows; do not flatten numeric tables.
        for start in range(0,len(text),1600):
            excerpt=text[start:start+2000].strip()
            if len(excerpt)>40: chunks.append((number,excerpt))
    if not chunks:
        raise ValueError('No readable text found. This PDF needs OCR before import.')
    folder=DATA/'documents'; folder.mkdir(parents=True,exist_ok=True)
    path=folder/f'{doc_id}.pdf'; path.write_bytes(content)
    with db() as c:
        # The transaction also makes concurrent imports idempotent.
        if c.execute('SELECT id FROM documents WHERE id=?',(doc_id,)).fetchone(): return doc_id
        c.execute('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?)',(doc_id,symbol,title,kind,period,source_url,str(path),now()))
        c.execute('INSERT INTO document_metadata VALUES (?,?,?,?)',(doc_id,discovery_url,published_at,verification))
        c.execute('INSERT OR IGNORE INTO companies VALUES (?,?,?,0)',(symbol,symbol,'Unclassified'))
        for page,text in chunks:
            cur=c.execute('INSERT INTO chunks(document_id,page,text) VALUES (?,?,?)',(doc_id,page,text))
            c.execute('INSERT INTO search(rowid,text) VALUES (?,?)',(cur.lastrowid,text))
    return doc_id

STOP={'the','and','what','does','this','that','with','from','have','company','tell','about','were','which','their','into','they','how','has','its','for','are','was','can','you','why','did'}
def retrieve(symbol,question,document_id=None,limit=10,periods=None):
    symbol=ticker(symbol)
    terms=[w for w in re.findall(r'[a-zA-Z]{3,}',question.lower()) if w not in STOP]
    if not terms: terms=['revenue','profit','business','cash']
    expansions={'business':['segment','products','services'],'drivers':['demand','revenue','margin'],'growth':['revenue','demand'],'debt':['borrowings','liquidity'],'cash':['flows','operating','working','capital'],'guidance':['outlook','expect','guidance'],'promised':['guidance','outlook'],'risks':['risk','uncertainty'],'margins':['margin','cost','utilisation']}
    expansions.update(businesses=['business','segment','products','services'],segments=['segment','business','services'],drives=['demand','revenue'])
    terms=list(dict.fromkeys(terms+[v for t in terms for v in expansions.get(t,[])]))[:20]
    match=' OR '.join('"'+t+'"' for t in terms)
    clause='d.id=?' if document_id else "d.kind IN ('annual_report','transcript')"
    params=[symbol]+([document_id] if document_id else [])
    if periods:
        clause+=' AND d.period IN ('+','.join('?' for _ in periods)+')'
        params+=list(periods)
    eligible=rows(f'SELECT d.id FROM documents d WHERE d.ticker=? AND {clause} ORDER BY d.period DESC,d.created_at DESC',params)
    candidates=[]; promoted=set()
    for doc in eligible:
        candidates+=rows('''SELECT ch.id,ch.page,ch.text,d.id document_id,d.title,d.kind,d.period,d.source_url,bm25(search) rank
          FROM search JOIN chunks ch ON ch.id=search.rowid JOIN documents d ON d.id=ch.document_id
          WHERE search MATCH ? AND d.id=? ORDER BY rank LIMIT 30''',[match,doc['id']])
        if 'cash' in terms and any(t in terms for t in ('profit','operating','flows')):
            # Prefer an actual statement heading to an audit discussion or a cash-balance note.
            table_candidates=rows('''SELECT ch.id,ch.page,ch.text,d.id document_id,d.title,d.kind,d.period,d.source_url,bm25(search) rank
              FROM search JOIN chunks ch ON ch.id=search.rowid JOIN documents d ON d.id=ch.document_id
              WHERE search MATCH ? AND d.id=? AND d.kind='annual_report' ORDER BY rank LIMIT 60''',
              ['"statement of cash flows" OR "statement of cash flow" OR "cash flow from operating activities"',doc['id']])
            headers=[r for r in table_candidates if re.search(r'(?:^|\n)(?:(?:consolidated|standalone)\s+)?statement\s+of\s+cash\s+flows?\b|(?:^|\n)A\.\s*cash\s*flow\s*from\s*operating',r['text'],re.I)
                     and re.search(r'(?im)^(?:net\s+)?profit[^\n]{0,150}[ \t]+\(?\d[\d,.() \t]*$',r['text'])]
            if headers:
                header=min(headers,key=lambda r:('consolidated' not in r['text'][:500].lower(),r['page']))
                promoted.add(header['id']);candidates.append(header)
    candidates.sort(key=lambda r:(r['id'] not in promoted,r['rank']))
    # Round-robin documents so a long annual report cannot swallow every call period.
    groups={}
    for row in candidates:
        group=groups.setdefault(row['document_id'],[])
        words=set(re.findall(r'\w+',row['text'].lower()))
        if any(row['text']==old['text'] or (row['page']==old['page'] and len(words & previous)/max(1,min(len(words),len(previous)))>.85) for old,previous in group): continue
        group.append((row,words))
    selected=[]
    for offset in range(limit):
        for group in groups.values():
            if offset<len(group): selected.append(group[offset][0])
            if len(selected)>=limit: return selected
    return selected

def coverage(symbol):
    documents=rows('''SELECT d.id,d.title,d.kind,d.period,d.source_url,d.created_at retrieved_at,
      m.discovery_url,m.published_at,COALESCE(m.verification,'legacy_import') verification,
      (SELECT max(page) FROM chunks WHERE document_id=d.id) pages
      FROM documents d LEFT JOIN document_metadata m ON m.document_id=d.id WHERE d.ticker=?
      ORDER BY d.period DESC,d.created_at DESC''',(ticker(symbol),))
    annual=[d for d in documents if d['kind']=='annual_report']
    transcripts=[d for d in documents if d['kind']=='transcript']
    gaps=[]
    if not annual: gaps.append('No annual report indexed.')
    if len({d['period'] for d in transcripts if d['period']})<2: gaps.append('Fewer than two distinct transcript periods indexed.')
    if any(not d['period'] for d in annual+transcripts): gaps.append('Some documents have no verified reporting period.')
    return {'ticker':ticker(symbol),'documents':documents,'annual_reports':len(annual),'transcripts':len(transcripts),
            'periods':sorted({d['period'] for d in annual+transcripts if d['period']},reverse=True),
            'gaps':gaps,'notice':'Coverage describes indexed documents; latest-period completeness is not established.'}

def change(current,previous):
    if previous is None or previous<=0 or current is None: return None
    return round((current/previous-1)*100,2)
