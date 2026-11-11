"""One local scheduler, persisted refresh history, and idempotent in-app alerts."""
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import fcntl
import hashlib
import json
import os
import threading
import uuid
import store
import connectors
from diagnostics import failure

_locks={'filings':threading.Lock(),'prices':threading.Lock()}

def _alert(c,symbol,kind,identity,title,reason,observed,event_id=None):
    return c.execute('INSERT OR IGNORE INTO alerts(id,ticker,kind,identity,title,reason,observed_at,created_at,event_id) VALUES (?,?,?,?,?,?,?,?,?)',
      (hashlib.sha256(identity.encode()).hexdigest()[:24],symbol,kind,identity,title,reason,observed,store.now(),event_id)).rowcount

def create_alerts(kind,result):
    config=store.settings(); added=0
    with store.db() as c:
        if kind=='filings':
            for eid in result.get('event_ids',[]):
                e=c.execute('SELECT * FROM events WHERE id=? AND archive=0',(eid,)).fetchone()
                if not e: continue
                seen=c.execute('INSERT OR IGNORE INTO monitor_state VALUES (?,?)',('event:'+eid,store.now())).rowcount
                if seen and e['category'] in config['categories']:
                    added+=_alert(c,e['ticker'],'filing','filing:'+eid,e['title'],e['category']+' is one of your watched categories.',e['published'],eid)
        else:
            for row in c.execute('SELECT p.* FROM prices p JOIN companies c ON c.ticker=p.ticker WHERE c.portfolio=1').fetchall():
                if row['ticker'] not in result.get('updated_tickers',[]): continue
                p=json.loads(row['data']); identity='price:'+row['ticker']+':'+p['date']
                # Mark even nonqualifying sessions, preventing retroactive threshold alerts.
                seen=c.execute('INSERT OR IGNORE INTO monitor_state VALUES (?,?)',(identity,store.now())).rowcount
                if not seen or p.get('corporate_action'): continue
                reasons=[]
                if p.get('change_pct') is not None and abs(p['change_pct'])>=config['price_threshold']: reasons.append(f"Price moved {p['change_pct']:+.2f}% (threshold ±{config['price_threshold']:g}%).")
                if p.get('volume_ratio') is not None and p['volume_ratio']>=config['volume_threshold']: reasons.append(f"Volume was {p['volume_ratio']:g}× the preceding 20 sessions (threshold {config['volume_threshold']:g}×).")
                if reasons: added+=_alert(c,row['ticker'],'price',identity,row['ticker']+' · unusual completed session',' '.join(reasons),p['date'])
    return added

def run_refresh(kind,days=7):
    if not _locks[kind].acquire(blocking=False): return {'skipped':True,'notice':'A refresh for this source is already running.'}
    rid=uuid.uuid4().hex; start=store.now()
    try:
        with store.db() as c:
            c.execute('INSERT INTO refresh_runs(id,source,started_at,status,window_start,window_end) VALUES (?,?,?,?,?,?)',
              (rid,kind,start,'running',(datetime.now(timezone.utc)-timedelta(days=days)).isoformat() if kind=='filings' else None,start))
        try:
            result=connectors.refresh_filings(days) if kind=='filings' else connectors.refresh_prices()
            result['alerts_created']=create_alerts(kind,result)
            status='partial' if result.get('partial') or (result.get('failed') and result.get('updated')) else 'failed' if result.get('failed') else 'completed'
            with store.db() as c:
                c.execute('UPDATE refresh_runs SET finished_at=?,status=?,result=? WHERE id=?',(store.now(),status,json.dumps(result),rid))
            result['refresh_id']=rid; result['status']=status
            return result
        except Exception as exc:
            error=failure(exc)
            with store.db() as c:
                c.execute('UPDATE refresh_runs SET finished_at=?,status=?,error_code=?,error=? WHERE id=?',(store.now(),'failed',error['code'],error['message'],rid))
            raise ValueError(error['message']) from None
    finally:
        _locks[kind].release()

def source_health():
    result={}
    for source in ('filings','prices'):
        latest=store.rows('SELECT * FROM refresh_runs WHERE source=? ORDER BY started_at DESC LIMIT 1',(source,))
        success=store.rows("SELECT finished_at FROM refresh_runs WHERE source=? AND status='completed' ORDER BY finished_at DESC LIMIT 1",(source,))
        entry=latest[0] if latest else {'status':'never_refreshed'}
        if entry.get('result'): entry['result']=json.loads(entry['result'])
        entry['last_success']=success[0]['finished_at'] if success else None
        result[source]=entry
    return result

class Monitor:
    def __init__(self):
        self.stop_event=threading.Event(); self.thread=None; self.lockfile=None
    def start(self):
        if os.getenv('FINN_DISABLE_MONITOR')=='1': return
        store.DATA.mkdir(parents=True,exist_ok=True)
        self.lockfile=(store.DATA/'monitor.lock').open('a')
        try: fcntl.flock(self.lockfile,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            self.lockfile.close(); self.lockfile=None; return
        self.thread=threading.Thread(target=self.loop,name='finn-monitor',daemon=True); self.thread.start()
    def due(self,kind,current):
        last=store.rows('SELECT started_at,status,finished_at FROM refresh_runs WHERE source=? ORDER BY started_at DESC LIMIT 1',(kind,))
        if last and (current-datetime.fromisoformat(last[0]['started_at'])).total_seconds()<900: return False
        if kind=='filings': return True
        local=current.astimezone(ZoneInfo('Asia/Kolkata'))
        if local.weekday()>4 or local.hour<16: return False
        successes=store.rows("SELECT finished_at FROM refresh_runs WHERE source='prices' AND status='completed' ORDER BY finished_at DESC LIMIT 1")
        return not successes or datetime.fromisoformat(successes[0]['finished_at']).astimezone(local.tzinfo).date()<local.date()
    def loop(self):
        try:
            while not self.stop_event.wait(5):
                if not store.settings().get('monitoring_enabled',True): continue
                for kind in ('filings','prices'):
                    if self.stop_event.is_set(): return
                    if self.due(kind,datetime.now(timezone.utc)):
                        try: run_refresh(kind,7)
                        except Exception: pass  # run_refresh persisted a sanitised error.
        finally:
            if self.lockfile: self.lockfile.close()
    def stop(self):
        self.stop_event.set()
        if self.thread: self.thread.join(timeout=1)
        # Keep the lease until an in-flight request finishes.
        if self.lockfile and not self.thread: self.lockfile.close()
