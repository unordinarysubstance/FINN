"""Browser checks against a temporary FINN database copy; no model/feed calls."""
import argparse
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parent

def clone_database(source,destination):
    destination.parent.mkdir(parents=True,exist_ok=True)
    # A read-only connection and SQLite backup preserve a consistent source snapshot.
    with sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True) as src,sqlite3.connect(destination) as dest:
        src.backup(dest)

def run_viewport(browser,base,viewport,output,fixture_path):
    from playwright.sync_api import expect
    context=browser.new_context(base_url=base,viewport=viewport)
    page=context.new_page();page.set_default_timeout(20000)
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    report={'viewport':viewport,'checks':[],'screenshots':[]}
    def record(name):report['checks'].append(name)
    def snapshot(name):
        width=page.evaluate('document.documentElement.scrollWidth')
        if width>viewport['width']+1:raise AssertionError(f'{name}: page overflow {width}px > viewport {viewport["width"]}px')
        target=output/f'{viewport["width"]}-{name}.png'
        page.screenshot(path=str(target),full_page=True)
        report['screenshots'].append(str(target))
    def visit(route,heading):
        page.goto(base+'/#'+route)
        expect(page.locator('#main')).to_contain_text(heading)
    try:
        visit('briefing','A little clarity.')
        snapshot('briefing-live');record('live briefing and width')
        page.get_by_role('button',name='Archive',exact=True).click()
        expect(page.locator('#main')).to_contain_text('ARCHIVE EXPLORER')
        save=page.locator('.event-card [data-action="save"]').first
        event_id=save.get_attribute('data-id');old_saved=save.get_attribute('data-saved')
        save.click()
        expect(page.locator(f'.event-card [data-action="save"][data-id="{event_id}"]')).to_have_attribute('data-saved','0' if old_saved=='1' else '1')
        record('saved event updates')
        page.locator('.event-card [data-action="event"]').first.click()
        expect(page.locator('.detail-title')).to_be_visible()
        assert page.locator('.contact-card').count()>0,'Event has no integrated network suggestions'
        original=page.get_by_role('link',name='↗ Open original filing')
        response=page.request.get(base+original.get_attribute('href'))
        assert response.ok and response.body().startswith(b'%PDF-'),'Original PDF cannot be opened'
        record('event detail, PDF and network');snapshot('event')

        visit('research','Follow the evidence.')
        page.locator('#research-ticker').fill('TCS');page.locator('#research-ticker').press('Tab')
        expect(page.locator('#coverage')).to_contain_text('TCS')
        page.locator('#question').fill('What are the main business segments?')
        page.locator('#research-form button.primary').click()
        expect(page.locator('#research-result')).to_contain_text('Source evidence',timeout=60000)
        assert page.locator('#research-result .source-card').count()>0,'No source passages rendered'
        record('research progress, evidence and primary coverage');snapshot('research-evidence')
        page.get_by_role('button',name='＋ Add a primary source').click()
        page.locator('#upload-symbol').fill('TCS');page.locator('#upload-kind').select_option('filing')
        page.locator('#upload-period').fill('2025');page.locator('#upload-title').fill('Existing reviewed TCS archive filing')
        page.locator('#upload-file').set_input_files(str(fixture_path))
        page.locator('#upload-form input[name="identity_confirmed"]').check()
        page.locator('#upload-form button.primary').click()
        expect(page.locator('#modal')).not_to_be_visible(timeout=60000)
        expect(page.locator('#research-scope')).not_to_have_value('')
        record('PDF upload and filing scope')

        visit('network','Your network knows more.')
        page.locator('#network-query').fill('IT Services');page.locator('#network-form button').click()
        expect(page.locator('.contact-card').first).to_be_visible()
        kavya=page.locator('[data-action="person"][data-id="p3"]')
        if kavya.count():
            kavya.click();expect(page.locator('#modal-body')).to_contain_text('You → Rohan Shah → Kavya Rao')
            page.keyboard.press('Escape');expect(page.locator('#modal')).not_to_be_visible()
            record('second-degree connection path and Escape')
        snapshot('network')
        page.locator('#network-query').fill('QA-NO-MATCH-4967');page.locator('#network-form button').click()
        expect(page.locator('#main')).to_contain_text('No matches yet.')
        record('network empty state')
        page.get_by_role('button',name='Import contacts JSON').click()
        page.locator('#contact-json').set_input_files(str(ROOT/'examples'/'contacts.json'))
        page.locator('#contact-import-form button.primary').click()
        expect(page.locator('#modal')).not_to_be_visible()
        expect(page.locator('.contact-card').first).to_be_visible()
        record('structured contact import')

        visit('portfolio','Keep the right companies close.')
        assert page.locator('tbody tr').count()>=15,'Portfolio has fewer than 15 companies'
        record('portfolio table');snapshot('portfolio')
        page.locator('#settings-button').click()
        page.locator('#price-limit').fill('6.5');page.locator('#volume-limit').fill('2.5')
        page.locator('#settings-form button.primary').click()
        expect(page.locator('#modal')).not_to_be_visible()
        settings=page.request.get(base+'/api/overview').json()['settings']
        assert settings['price_threshold']==6.5 and settings['volume_threshold']==2.5
        record('settings persistence in QA database')
        page.locator('#alerts-button').click();expect(page.locator('#modal')).to_be_visible()
        before=page.request.get(base+'/api/notifications').json()['unread']
        mark=page.get_by_role('button',name='Mark read',exact=True)
        if mark.count():
            mark.first.click()
            expect(page.locator('#modal-body')).to_contain_text(str(before-1)+' unread')
            assert page.request.get(base+'/api/notifications').json()['unread']==before-1
            record('persisted alert read state')
        snapshot('alerts');page.keyboard.press('Escape')
        visit('research','Follow the evidence.')
        page.locator('#research-ticker').fill('INVALID/TICKER');page.locator('#research-ticker').press('Tab')
        page.locator('#question').fill('What is revenue?');page.locator('#research-form button.primary').click()
        expect(page.locator('#research-result')).to_contain_text('Enter an NSE symbol')
        record('visible research failure state');snapshot('research-error')
        assert not errors,'Uncaught browser errors: '+str(errors)
        report['status']='passed'
    except Exception as exc:
        report['status']='failed';report['error']=str(exc)
        try:page.screenshot(path=str(output/f'{viewport["width"]}-failure.png'),full_page=True)
        except Exception:pass
    finally:
        report['page_errors']=errors;context.close()
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--channel',default='chrome')
    args=parser.parse_args()
    try:from playwright.sync_api import sync_playwright
    except ImportError:raise SystemExit('Install browser tools first: python3 -m pip install -r requirements-dev.txt')
    values=dotenv_values(ROOT/'.env')
    data=Path(os.environ.get('FINN_DATA_DIR') or values.get('FINN_DATA_DIR') or ROOT/'data').resolve()
    if not (data/'finn.sqlite3').exists():raise SystemExit('Start FINN once to initialise its data, then run browser QA.')
    output=data/'verification'/'browser';output.mkdir(parents=True,exist_ok=True)
    report={'checked_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'database':'temporary snapshot','ai_calls_enabled':False,'monitoring_enabled':False,'viewports':[]}
    process=None
    # No API key is supplied to either the QA server or browser driver.
    os.environ['OPENAI_API_KEY']=''
    try:
        with tempfile.TemporaryDirectory(prefix='finn-browser-qa-') as temp:
            snapshot=Path(temp)/'finn.sqlite3';clone_database(data/'finn.sqlite3',snapshot)
            with sqlite3.connect(snapshot) as c:
                row=c.execute("SELECT path FROM documents WHERE ticker='TCS' AND kind='filing' LIMIT 1").fetchone()
            if not row:raise ValueError('The reviewed TCS archive filing is needed for the PDF upload check.')
            fixture_path=Path(row[0]);fixture_path=fixture_path if fixture_path.is_absolute() else ROOT/fixture_path
            with socket.socket() as port_probe:
                port_probe.bind(('127.0.0.1',0));port=port_probe.getsockname()[1]
            base=f'http://127.0.0.1:{port}'
            env={**os.environ,'FINN_DATA_DIR':temp,'FINN_DISABLE_MONITOR':'1','OPENAI_API_KEY':'','PYTHONUNBUFFERED':'1'}
            with (output/'server.log').open('w') as log:
                process=subprocess.Popen([sys.executable,'-m','uvicorn','app:app','--host','127.0.0.1','--port',str(port),'--workers','1','--log-level','warning'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
                try:
                    deadline=time.monotonic()+90
                    while True:
                        if process.poll() is not None:raise RuntimeError('QA server stopped; inspect private server.log.')
                        try:
                            with urlopen(base+'/api/health',timeout=2) as response:
                                if response.status==200:break
                        except OSError:
                            if time.monotonic()>deadline:raise RuntimeError('QA server did not become ready.')
                            time.sleep(.3)
                    with sync_playwright() as p:
                        browser=p.chromium.launch(channel=args.channel,headless=True)
                        try:
                            for viewport in ({'width':1440,'height':1000},{'width':390,'height':844}):
                                report['viewports'].append(run_viewport(browser,base,viewport,output,fixture_path))
                        finally:browser.close()
                finally:
                    process.terminate()
                    try:process.wait(timeout=8)
                    except subprocess.TimeoutExpired:process.kill();process.wait()
        report['status']='passed' if all(v['status']=='passed' for v in report['viewports']) else 'failed'
    except Exception as exc:report.update(status='failed',error=str(exc))
    target=output/'report.json';target.write_text(json.dumps(report,indent=2))
    print('Browser report:',target)
    print('Result:',report['status'])
    for result in report['viewports']:print(result['viewport']['width'],'px:',result['status'],result.get('error',''))
    if report.get('error'):print(report['error'])
    return 0 if report['status']=='passed' else 1

if __name__=='__main__':sys.exit(main())
