"""Explicitly historical, real filings; explicitly synthetic network. No fake market data."""
import json
from store import ROOT,db,rows,import_pdf

COMPANIES=[('RELIANCE','Reliance Industries','Energy & Retail'),('TCS','Tata Consultancy Services','IT Services'),('HDFCBANK','HDFC Bank','Banking'),('INFY','Infosys','IT Services'),('BHARTIARTL','Bharti Airtel','Telecom'),('ITC','ITC','Consumer'),('LT','Larsen & Toubro','Industrials'),('HINDUNILVR','Hindustan Unilever','Consumer'),('BAJFINANCE','Bajaj Finance','Lending'),('HCLTECH','HCL Technologies','IT Services'),('SBIN','State Bank of India','Banking'),('LICI','Life Insurance Corporation','Insurance'),('TMPV','Tata Motors Passenger Vehicles','Automotive'),('SUNPHARMA','Sun Pharmaceutical','Healthcare'),('TITAN','Titan Company','Consumer'),('DEEPAKNTR','Deepak Nitrite','Chemicals'),('DIXON','Dixon Technologies','Electronics'),('AUBANK','AU Small Finance Bank','Banking')]

# Reviewed against the local source pages, not model-generated news.
EVENTS=[
 ('RELIANCE','2025-07-18','Profit growth deserves a closer look',95,'Reported PAT rose 75.8% YoY. The release also discloses ₹8,924 crore of profit from sales of listed investments. Inspect the recurring drivers before extrapolating growth.'),
 ('TCS','2025-07-10','Strong deal wins, softer underlying demand',90,'Revenue rose 1.3% in rupees but declined 3.1% in constant currency YoY. TCS reported $9.4 billion in contract value and 100.3% cash conversion.'),
 ('HCLTECH','2025-10-13','Quarterly results and ₹12 interim dividend',75,'The board approved September-quarter results and a ₹12 per-share interim dividend. Review the original consolidated and standalone statements.'),
 ('HINDUNILVR','2025-07-31','June-quarter results approved',65,'The board approved June-quarter standalone and consolidated results. The filing includes the financial statements and limited review reports.'),
 ('LICI','2025-11-06','A new results filing to review',60,'Archived company filing dated 6 November 2025. Open the source for the reported figures and disclosures.')]

PEOPLE=[
 ('p1','Ananya Mehta','Former finance lead','RELIANCE','Energy & Retail',['retail margins','capital allocation','cash flow'],'2018–2023','Former colleague','IIM Ahmedabad','What part of the earnings improvement is recurring?', ['p4']),
 ('p2','Rohan Shah','Enterprise technology advisor','TCS','IT Services',['deal conversion','AI spending','IT budgets'],'2016–2022','University acquaintance','IIT Kanpur','Are signed deals converting into revenue as expected?', ['p3']),
 ('p3','Kavya Rao','Former delivery director','INFY','IT Services',['delivery economics','IT budgets','margins'],'2015–2021','Introduction through Rohan Shah','IIT Madras','What is changing in client budgets and project starts?', []),
 ('p4','Neel Desai','Telecom strategy specialist','BHARTIARTL','Telecom',['ARPU','5G','subscriber growth'],'2017–2022','Former colleague','IIM Ahmedabad','How sustainable are the recent gains in monetisation?', []),
 ('p5','Meera Iyer','Consumer sector operator','HINDUNILVR','Consumer',['distribution','rural demand','volume growth'],'2014–2020','Professional acquaintance','IIM Bangalore','What are distributors seeing in underlying demand?', []),
 ('p6','Arjun Sethi','Former credit risk manager','HDFCBANK','Banking',['asset quality','deposits','credit risk'],'2018–2024','Former colleague','IIT Kanpur','Are credit costs and deposit competition changing?', []),
 ('p7','Isha Kapoor','Industrial projects advisor','LT','Industrials',['capex','execution','working capital'],'2016–2023','Professional acquaintance','BITS Pilani','How much of the order book is ready for execution?', []),
 ('p8','Dev Menon','Specialty chemicals operator','DEEPAKNTR','Chemicals',['specialty chemicals','capacity','utilisation'],'2019–2024','University acquaintance','IIT Kanpur','What is driving capacity utilisation and pricing?', []),
 ('p9','Tara Nair','Former lending product lead','BAJFINANCE','Lending',['rural lending','credit risk','consumer finance'],'2017–2023','Professional acquaintance','IIM Lucknow','Where are underwriting conditions changing?', []),
 ('p10','Vikram Rao','Electronics manufacturing advisor','DIXON','Electronics',['semiconductors','electronics','supply chains'],'2018–2023','Professional acquaintance','IIT Bombay','Which supply constraints are affecting execution?', [])]

def seed():
    with db() as c:
        for company in COMPANIES: c.execute('INSERT OR IGNORE INTO companies VALUES (?,?,?,1)',company)
        seed_people=[] if (c.execute("SELECT 1 FROM monitor_state WHERE key='contacts_initialized'").fetchone() or c.execute('SELECT 1 FROM contacts LIMIT 1').fetchone()) else PEOPLE
        for pid,name,role,company,sector,tags,tenure,relationship,education,question,links in seed_people:
            data=dict(id=pid,name=name,role=role,company=company,sector=sector,tags=tags,tenure=tenure,relationship=relationship,education=education,question=question,links=links,synthetic=True,degree=2 if pid=='p3' else 1)
            c.execute('INSERT OR IGNORE INTO contacts VALUES (?,?)',(pid,json.dumps(data)))
        c.execute("INSERT OR IGNORE INTO monitor_state VALUES ('contacts_initialized','1')")
    assets=ROOT.parent/'CS787-main'/'company_assets'
    docs={}
    for symbol,name,_ in COMPANIES:
        path=assets/f'{symbol}.NS'/f'{symbol}.NS.pdf'
        if not path.exists(): path=ROOT/'demo_documents'/f'{symbol}.pdf'
        if path.exists(): docs[symbol]=import_pdf(path.read_bytes(),symbol,f'{name} · archived 2025 filing','filing','2025')
    with db() as c:
        for symbol,date,title,priority,summary in EVENTS:
            if symbol in docs:
                c.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?,?,?,?,?,0,0)',(f'archive-{symbol}',symbol,title,'Results',date+'T12:00:00+05:30',priority,summary,docs[symbol],'',1))

def contacts(symbol='',query=''):
    from network import contacts as match
    return match(symbol,query)
