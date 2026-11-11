"""Create a reviewable source bundle using an explicit allowlist, never runtime data."""
import hashlib
import json
from pathlib import Path
import zipfile
import sqlite3
import tempfile
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent/'.env',override=False)
import store
from seed import COMPANIES

ROOT=Path(__file__).resolve().parent
FILES=['app.py','connectors.py','diagnostics.py','manage.py','monitoring.py','network.py','research.py','seed.py','store.py','package_submission.py','browser_qa.py','requirements-dev.txt','requirements.txt','README.md','VERIFICATION.md','IMPLEMENTATION_PLAN.md','.gitignore','.env.example','Dockerfile','.dockerignore']

def public_index(entries,folder):
    """Export only allowlisted issuer PDFs and their extracted text, never investor state."""
    runtime=store.DATA/'finn.sqlite3'
    if not runtime.exists():
        template=ROOT/'demo_data'/'public.sqlite3'
        if not template.exists():return 0
        with sqlite3.connect(template.resolve().as_uri()+'?mode=ro',uri=True) as c:
            paths=[r[0] for r in c.execute('SELECT path FROM documents')]
            for table in ('contacts','events','prices','jobs','alerts','refresh_runs','cache','monitor_state'):
                assert c.execute(f'SELECT count(*) FROM {table}').fetchone()[0]==0,table
        for relative in paths:
            path=(ROOT/relative).resolve()
            if Path(relative).is_absolute() or not Path(relative).parts or Path(relative).parts[0] not in ('demo_documents','demo_primary') or path.suffix.lower()!='.pdf' or not path.is_relative_to(ROOT.resolve()) or not path.is_file():raise ValueError('Invalid bundled public-document path.')
            entries[relative]=path
        entries['demo_data/public.sqlite3']=template
        return sum(p.startswith('demo_primary/') for p in paths)
    registry=json.loads((ROOT/'examples'/'primary_sources.json').read_text())
    targets=[d for d in registry['documents']+registry.get('historical_fallbacks',[]) if d['identity_status']=='content_verified']
    selected=[]
    with sqlite3.connect(runtime.resolve().as_uri()+'?mode=ro',uri=True) as source:
        source.row_factory=sqlite3.Row
        for symbol,name,_ in COMPANIES:
            relative=f'demo_documents/{symbol}.pdf'
            if relative in entries:
                data=entries[relative].read_bytes();docid=hashlib.sha256(symbol.encode()+b'filing'+data).hexdigest()[:24]
                row=source.execute('SELECT * FROM documents WHERE id=?',(docid,)).fetchone()
                if row:selected.append((dict(row),relative,f'{name} · archived 2025 filing','2025','','',None))
        primary_count=0
        for item in targets:
            row=source.execute("""SELECT d.* FROM documents d JOIN document_metadata m ON m.document_id=d.id
              WHERE d.ticker=? AND d.kind=? AND d.period=? AND d.source_url=?
              AND m.verification IN ('manifest_and_content_checks','local_manifest_and_content_checks','bundled_public_source')""",(item['ticker'],item['kind'],item['period'],item['url'])).fetchone()
            if not row:continue
            row=dict(row);path=Path(row['path']);path=path if path.is_absolute() else ROOT/path
            data=path.read_bytes()
            expected=hashlib.sha256(item['ticker'].encode()+item['kind'].encode()+data).hexdigest()[:24]
            if expected!=row['id']:raise ValueError('Public PDF content hash does not match its indexed identity.')
            relative=f"demo_primary/{row['id']}.pdf";entries[relative]=path
            selected.append((row,relative,item['title'],item['period'],item['url'],item['discovery_url'],item.get('publication_date')))
            primary_count+=1
        if not selected:return 0
        previous=store.DATA
        try:
            store.DATA=folder;store.init(seed_demo=False)
        finally:store.DATA=previous
        with sqlite3.connect(folder/'finn.sqlite3') as dest:
            for company in COMPANIES:dest.execute('INSERT OR IGNORE INTO companies VALUES (?,?,?,1)',company)
            for row,relative,title,period,url,discovery,published in selected:
                dest.execute('INSERT OR IGNORE INTO companies VALUES (?,?,?,0)',(row['ticker'],row['ticker'],'Unclassified'))
                dest.execute('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?)',(row['id'],row['ticker'],title,row['kind'],period,url,relative,row['created_at']))
                dest.execute('INSERT INTO document_metadata VALUES (?,?,?,?)',(row['id'],discovery,published,'bundled_public_source'))
                for chunk in source.execute('SELECT id,page,text FROM chunks WHERE document_id=? ORDER BY id',(row['id'],)):
                    dest.execute('INSERT INTO chunks VALUES (?,?,?,?)',(chunk['id'],row['id'],chunk['page'],chunk['text']))
                    dest.execute('INSERT INTO search(rowid,text) VALUES (?,?)',(chunk['id'],chunk['text']))
            for table in ('contacts','events','prices','jobs','alerts','refresh_runs','cache','monitor_state'):
                assert dest.execute(f'SELECT count(*) FROM {table}').fetchone()[0]==0,table
        entries['demo_data/public.sqlite3']=folder/'finn.sqlite3'
        return primary_count


def package():
    output=ROOT/'dist';output.mkdir(exist_ok=True)
    entries={name:ROOT/name for name in FILES}
    for folder in ('static','tests','examples','docs'):
        for path in (ROOT/folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':entries[path.relative_to(ROOT).as_posix()]=path
    for symbol,*_ in COMPANIES:
        source=ROOT.parent/'CS787-main'/'company_assets'/f'{symbol}.NS'/f'{symbol}.NS.pdf'
        if not source.exists():source=ROOT/'demo_documents'/f'{symbol}.pdf'
        if source.exists():entries[f'demo_documents/{symbol}.pdf']=source
    manifest=[];target=output/'finn-submission.zip'
    with tempfile.TemporaryDirectory(prefix='finn-public-index-') as temporary:
        primary_count=public_index(entries,Path(temporary))
        missing=[name for name,path in entries.items() if not path.exists()]
        if missing:raise RuntimeError('Required publication files are missing: '+', '.join(missing))
        for name in entries:
            assert not any(part in ('data','.git','.aws','.codex','.agents','.venv','__pycache__') for part in Path(name).parts)
            assert name!='.env'
        secret=__import__('os').getenv('OPENAI_API_KEY','').encode()
        with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as bundle:
            for name,path in sorted(entries.items()):
                data=path.read_bytes()
                if secret and secret in data:raise ValueError('Configured API key detected in publication content.')
                bundle.writestr('finn/'+name,data)
                manifest.append({'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
            bundle.writestr('finn/PACKAGE_MANIFEST.json',json.dumps(manifest,indent=2))
    print('Bundle:',target)
    print('Files:',len(entries),'Archived public PDFs:',sum(n.startswith('demo_documents/') for n in entries),'Primary PDFs:',primary_count)
    print('Public document index included when available. Investor databases, profiles, alerts, caches and credentials are excluded.')
    return target

if __name__=='__main__':package()
