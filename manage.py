"""Repeatable local setup and honest live verification. Run `python3 manage.py --help`."""
import argparse
import io
import json
from pathlib import Path
import re
import sys
import socket
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent/'.env',override=False)
import store
import connectors
import monitoring
import seed
from diagnostics import failure
from pypdf import PdfReader
from research import research

QUESTIONS=[
 'What are the main businesses and segments, and what drives demand?',
 'What does management say about growth, margins, outlook and uncertainties?',
 'How does operating cash flow compare with profit, and what are the working-capital or debt risks?'
]

def validate_identity(content,item):
    reader=PdfReader(io.BytesIO(content))
    sample=' '.join((p.extract_text() or '') for p in reader.pages[:8]).lower()
    normal=' '.join(re.findall(r'[a-z0-9]+',sample))
    words=[w for w in re.findall(r'[a-z]+',item['company_name'].lower()) if w not in ('limited','ltd','the')]
    if not words or not all(w in normal.split() for w in words): raise ValueError('Company identity requires manual inspection.')
    markers=('annual report','integrated report','integrated annual') if item['kind']=='annual_report' else ('transcript','conference call','earnings call')
    if not any(marker in normal for marker in markers): raise ValueError('Document type requires manual inspection.')
    # The manifest has a human-inspected period. Fail closed if its year is absent from these bytes.
    match=re.search(r'20\d{2}',item['period'])
    if not match: raise ValueError('No verified reporting period in manifest.')
    year=int(match.group())
    if str(year) not in normal and str(year-1) not in normal: raise ValueError('Reporting year requires manual inspection.')

def local_filename(item):
    """A stable, safe inbox filename, independent of remote URL redirects."""
    return re.sub(r'[^A-Za-z0-9_-]+','-',item['ticker']+'-'+item['kind']+'-'+item['period']).strip('-')+'.pdf'

def prepare(manifest,include_historical=False,local_dir=None):
    content=json.loads(Path(manifest).read_text())
    items=content['documents']+(content.get('historical_fallbacks',[]) if include_historical else [])
    results=[]
    for item in items:
        record={'ticker':item['ticker'],'title':item['title'],'period':item['period'],'url':item['url'],'local_filename':local_filename(item)}
        if item['identity_status']!='content_verified' or not item['period']:
            record.update(status='manual_review_required');results.append(record);continue
        existing=store.rows('SELECT id FROM documents WHERE ticker=? AND source_url=? AND kind=?',(item['ticker'],item['url'],item['kind']))
        if existing:
            record.update(status='already_indexed',document_id=existing[0]['id']);results.append(record);continue
        try:
            if local_dir:
                path=Path(local_dir)/record['local_filename']
                if not path.is_file():
                    record.update(status='missing_local_file');results.append(record);continue
                if path.stat().st_size>store.pdf_limit(item['kind']): raise ValueError('Local PDF exceeds the size limit.')
                data=path.read_bytes();url=item['url']
            else:
                data,url=connectors.download(item['url'],max_bytes=store.pdf_limit(item['kind']))
            validate_identity(data,item)
            verification='local_manifest_and_content_checks' if local_dir else 'manifest_and_content_checks'
            doc=store.import_pdf(data,item['ticker'],item['title'],item['kind'],item['period'],url,item['discovery_url'],item.get('publication_date'),verification=verification)
            record.update(status='indexed',document_id=doc)
        except Exception as exc:record.update(status='failed',error=failure(exc))
        results.append(record)
    return {'checked_at':store.now(),'documents':results,'coverage':[store.coverage(s) for s in sorted({i['ticker'] for i in items})]}

def evaluate(symbols,question_indexes=None):
    indexes=list(question_indexes) if question_indexes is not None else list(range(1,len(QUESTIONS)+1))
    if not indexes or any(type(i) is not int or not 1<=i<=len(QUESTIONS) for i in indexes):raise ValueError('Unsupported evaluation question index.')
    answers=[]
    for symbol in symbols:
        for question_index in indexes:
            question=QUESTIONS[question_index-1]
            result=research(symbol,question)
            result['question_index']=question_index
            ids={c['id'] for c in result['citations']}
            valid=all(f['sources'] and all(s in ids for s in f['sources']) for f in result['findings'])
            result['automated_acceptance']=bool(result['mode']=='ai' and result['findings'] and valid and result['diagnostics'].get('reviewer_completed'))
            result['manual_review']='pending; inspect each finding against its cited passage and original page'
            answers.append(result)
    return {'checked_at':store.now(),'selection':{'symbols':symbols,'question_indexes':indexes},'answers':answers,'passed_automated':sum(a['automated_acceptance'] for a in answers),'required':len(answers),'manual_review_complete':False}

def verify(manifest,include_historical,symbols):
    """Run the live acceptance sequence, stopping early on a blocked runtime."""
    checks=[]
    for host in ('www.screener.in','api.openai.com','www.nseindia.com','query1.finance.yahoo.com'):
        try:
            socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
            checks.append({'host':host,'status':'resolved'})
        except OSError as exc: checks.append({'host':host,'status':'failed','error':failure(exc)})
    report={'checked_at':store.now(),'runtime':checks,'manual_review_complete':False}
    if all(c['status']=='failed' for c in checks):
        return {**report,'status':'blocked','next_action':'Run this command in a terminal with outbound HTTPS and DNS access. No acquisition or model calls were attempted.'}
    report['preparation']=prepare(manifest,include_historical)
    docs=store.rows("SELECT id FROM documents WHERE ticker='TCS' AND kind='filing' LIMIT 1")
    report['smoke_ai']=research('TCS','What revenue change and cash conversion does this filing report?',docs[0]['id'] if docs else None)
    report['feeds']={}
    for kind in ('filings','prices'):
        try: report['feeds'][kind]=monitoring.run_refresh(kind)
        except Exception: report['feeds'][kind]=monitoring.source_health()[kind]
    if report['smoke_ai']['mode']=='ai':
        report['evaluation']=evaluate(symbols)
    else:
        report['evaluation']={'status':'skipped','reason':'Resolve the AI smoke-check failure before running the full evaluation.',
            'passed_automated':0,'required':len(symbols)*len(QUESTIONS),'answers':[],'manual_review_complete':False}
    passed=(all(d['status'] in ('indexed','already_indexed') for d in report['preparation']['documents'])
      and report['smoke_ai']['mode']=='ai'
      and all(v.get('status')=='completed' for v in report['feeds'].values())
      and report['evaluation']['passed_automated']==report['evaluation']['required'])
    report['status']='automated_checks_passed' if passed else 'incomplete'
    report['next_action']='Inspect findings against cited original pages, resolve remaining coverage gaps, and complete browser/phone QA.'
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['status','prepare','evaluate','refresh','smoke-ai','verify'])
    parser.add_argument('--manifest',default=str(store.ROOT/'examples'/'primary_sources.json'))
    parser.add_argument('--include-historical',action='store_true')
    parser.add_argument('--local-dir',help='Import verified manifest PDFs from this inbox without network requests; see each record local_filename in the report.')
    parser.add_argument('--symbols',nargs='+',default=['TCS','INFY','RELIANCE','ASIANPAINT'])
    parser.add_argument('--question-index',type=int,choices=range(1,len(QUESTIONS)+1),help='Evaluate only this question (1 business, 2 outlook, 3 cash flow) to diagnose a specific failure.')
    parser.add_argument('--days',type=int,choices=[1,7,30,365],default=7,help='Requested announcement refresh window.')
    args=parser.parse_args()
    if args.local_dir and args.command!='prepare':parser.error('--local-dir is only supported for prepare')
    if args.question_index and args.command!='evaluate':parser.error('--question-index is only supported for evaluate')
    store.init();seed.seed()
    if args.command=='status':
        import os
        result={'ai_configured':bool(os.getenv('OPENAI_API_KEY')),'model':os.getenv('FINN_MODEL','gpt-4o-mini'),'coverage':[store.coverage(s) for s in args.symbols],'sources':monitoring.source_health()}
    elif args.command=='prepare':result=prepare(args.manifest,args.include_historical,args.local_dir)
    elif args.command=='evaluate':result=evaluate(args.symbols,[args.question_index] if args.question_index else None)
    elif args.command=='verify':result=verify(args.manifest,args.include_historical,args.symbols)
    elif args.command=='smoke-ai':
        docs=store.rows("SELECT id FROM documents WHERE ticker='TCS' AND kind='filing' LIMIT 1")
        result=research('TCS','What revenue change and cash conversion does this filing report?',docs[0]['id'] if docs else None)
    else:
        result={}
        for kind in ('filings','prices'):
            try:result[kind]=monitoring.run_refresh(kind,args.days)
            except Exception:result[kind]=monitoring.source_health()[kind]
    output=store.DATA/'verification';output.mkdir(parents=True,exist_ok=True)
    path=output/(args.command+'.json')
    if args.command=='evaluate' and path.exists():
        import hashlib
        previous=path.read_bytes();history=output/'history';history.mkdir(exist_ok=True)
        archived=history/('evaluate-'+hashlib.sha256(previous).hexdigest()[:16]+'.json')
        if not archived.exists():archived.write_bytes(previous)
    path.write_text(json.dumps(result,indent=2))
    print('Report:',path)
    if args.command=='smoke-ai': print(json.dumps({'mode':result['mode'],'diagnostics':result['diagnostics']},indent=2))
    elif args.command=='prepare':
        for r in result['documents']:print(r['ticker'],r['period'] or 'period unknown',r['status'],r.get('error',{}).get('message',''))
    elif args.command=='evaluate':print(f"AI answers passing structural checks: {result['passed_automated']}/{result['required']}; manual review pending.")
    elif args.command=='refresh':
        for key,value in result.items():print(key,value.get('status','unknown'))
    elif args.command=='verify':
        print(result['status']+': '+result['next_action'])
        if result.get('preparation'):
            docs=result['preparation']['documents']
            print('Documents:',sum(d['status'] in ('indexed','already_indexed') for d in docs),'available;',sum(d['status']=='manual_review_required' for d in docs),'need manual review')
            for d in docs:
                if d['status']=='failed':print('Document failure:',d['ticker'],d['period'],d['error']['message'])
        if result.get('smoke_ai'):
            print('AI smoke:',result['smoke_ai']['mode'])
            if result['smoke_ai']['diagnostics'].get('error'):print(json.dumps(result['smoke_ai']['diagnostics']['error'],indent=2))
        for kind,value in result.get('feeds',{}).items():print('Feed:',kind,value.get('status'))
        if result.get('evaluation',{}).get('status')=='skipped':print('Evaluation skipped:',result['evaluation']['reason'])
    else:print('AI configured:',result['ai_configured'],'Model:',result['model']);print('Coverage:',[(c['ticker'],c['annual_reports'],c['transcripts']) for c in result['coverage']])
    if args.command=='smoke-ai' and result['mode']!='ai':return 1
    if args.command=='evaluate' and result['passed_automated']!=result['required']:return 1
    if args.command=='prepare' and any(r['status'] not in ('indexed','already_indexed') for r in result['documents']):return 1
    if args.command=='refresh' and any(v.get('status')!='completed' for v in result.values()):return 1
    if args.command=='verify' and result['status']!='automated_checks_passed':return 1
    return 0

if __name__=='__main__':sys.exit(main())
