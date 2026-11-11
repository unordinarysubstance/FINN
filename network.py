"""Structured, explicitly known relationships; overlaps never become invented edges."""
from datetime import date
import json
import re
from pydantic import BaseModel,Field,ConfigDict,model_validator
from store import db,rows,ticker

class Employment(BaseModel):
    model_config=ConfigDict(extra='forbid')
    company:str=Field(min_length=1,max_length=100)
    role:str=Field(min_length=1,max_length=150)
    start:date
    end:date|None=None
    @model_validator(mode='after')
    def chronological(self):
        if self.end and self.end<self.start: raise ValueError('Employment end precedes start.')
        return self

class Contact(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id:str=Field(pattern=r'^[A-Za-z0-9_-]{1,60}$')
    name:str=Field(min_length=1,max_length=100)
    role:str=Field(min_length=1,max_length=150)
    company:str=Field(min_length=1,max_length=100)
    sector:str=Field(default='',max_length=100)
    tags:list[str]=Field(default_factory=list,max_length=30)
    education:str=Field(default='',max_length=300)
    relationship:str=Field(min_length=1,max_length=300)
    degree:int=Field(ge=1,le=2)
    links:list[str]=Field(default_factory=list,max_length=100)
    employment:list[Employment]=Field(min_length=1,max_length=30)
    synthetic:bool=True
    question:str=Field(default='',max_length=500)
    @model_validator(mode='after')
    def bounded_strings(self):
        if any(len(v)>100 for v in self.tags+self.links): raise ValueError('Tags and relationship IDs must be at most 100 characters.')
        return self

class ContactImport(BaseModel):
    model_config=ConfigDict(extra='forbid')
    contacts:list[Contact]=Field(min_length=1,max_length=500)
    replace:bool=False

def import_contacts(body):
    incoming=[p.model_dump(mode='json') for p in body.contacts]
    if len({p['id'] for p in incoming})!=len(incoming): raise ValueError('Duplicate contact IDs.')
    old={p['id']:json.loads(p['data']) for p in rows('SELECT * FROM contacts')} if not body.replace else {}
    combined={**old,**{p['id']:p for p in incoming}}
    for p in combined.values():
        if p['id'] in p.get('links',[]) or any(link not in combined for link in p.get('links',[])):
            raise ValueError('Every relationship must reference another imported or existing contact.')
    for p in combined.values():
        if p.get('degree')==2 and not connection_path(p['id'],combined):
            raise ValueError('Second-degree contacts need an explicit relationship to a first-degree contact.')
    with db() as c:
        if body.replace: c.execute('DELETE FROM contacts')
        for p in incoming:
            p['tenure']='; '.join(e['start'][:4]+'–'+(e['end'][:4] if e['end'] else 'present') for e in p['employment'])
            if not p['question']: p['question']='What has your experience with '+(', '.join(p['tags'][:2]) or p['role'])+' taught you to investigate?'
            c.execute('INSERT OR REPLACE INTO contacts VALUES (?,?)',(p['id'],json.dumps(p)))
        c.execute("INSERT OR REPLACE INTO monitor_state VALUES ('contacts_initialized','1')")
    return {'imported':len(incoming),'total':len(combined)}

def connection_path(pid,people):
    person=people[pid]
    if person.get('degree',1)==1: return ['You',person['name']]
    for first in people.values():
        if first.get('degree',1)==1 and (pid in first.get('links',[]) or first['id'] in person.get('links',[])):
            return ['You',first['name'],person['name']]
    return []

def normalise(p):
    p=dict(p)
    if not p.get('employment'):
        years=re.findall(r'\d{4}',p.get('tenure',''))
        p['employment']=[{'company':p['company'],'role':p['role'],'start':years[0]+'-01-01' if years else '', 'end':years[1]+'-12-31' if len(years)>1 else None}]
        p['employment_date_precision']='year'
    return p

def contacts(symbol='',query=''):
    people={p['id']:normalise(json.loads(p['data'])) for p in rows('SELECT * FROM contacts')}
    companies=rows('SELECT * FROM companies WHERE ticker=?',(symbol,)) if symbol else []
    sector=companies[0]['sector'] if companies else ''
    company_names={symbol.upper()}
    if companies: company_names.add(companies[0]['name'].upper())
    tokens=re.findall(r'[a-z0-9&-]{3,}',query.lower())
    result=[]
    for p in people.values():
        score=0; reasons=[]
        history=p['employment']
        matches=[e for e in history if e['company'].upper() in company_names] if symbol else []
        if matches:
            score+=100
            e=matches[0]; reasons.append(f"Worked at {e['company']} ({e['start'][:4]}–{e['end'][:4] if e['end'] else 'present'}), {e['role']}")
        elif sector and p.get('sector')==sector:
            score+=40; reasons.append('Experience in '+sector)
        text=' '.join([p['name'],p['company'],p['role'],p.get('sector',''),p.get('education',''),*p.get('tags',[]),*[e['company']+' '+e['role'] for e in history]]).lower()
        matched=[t for t in tokens if t in text]
        if matched: score+=len(matched)*10; reasons.append('Matches: '+', '.join(matched))
        if not symbol and not query: score=1
        if score:
            path=connection_path(p['id'],people)
            result.append({**p,'score':score,'reason':'; '.join(reasons) or p['relationship'],'connection_path':path,
                'connection_notice':'Explicitly recorded relationship' if path else 'No known introduction path'})
    return sorted(result,key=lambda x:-x['score'])
