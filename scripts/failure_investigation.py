"""Controlled replay interruption, genuine Flask/browser evidence and recovery proof.

Source Archive stays immutable. Replayed arrivals are written to a dedicated
SQLite test database. No fake readings or gap interpolation are used.
"""
from __future__ import annotations
import csv
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence'
DB = ROOT / 'state' / 'failure_monitor.db'
PAUSE = ROOT / 'state' / 'pause.flag'
LOG = ROOT / 'logs' / 'failure_monitor.jsonl'
PORT = os.environ.get('FAILURE_TEST_PORT', '5139')
BASE = f'http://127.0.0.1:{PORT}'
REQUIRED = ('FAILURE_INJECTED', 'SOURCE_PAUSED', 'STALE_INPUT', 'INPUT_FAILED',
            'RECOVERY_ACTION', 'SOURCE_RESUMED', 'HEALTH_RECOVERED')


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def fetch(path='/api/status'):
    with urlopen(BASE + path, timeout=3) as response:
        return json.loads(response.read().decode('utf-8'))


def wait_for(label, predicate, timeout=25):
    end = time.monotonic() + timeout
    last = None
    while time.monotonic() < end:
        try:
            last = fetch()
            if predicate(last):
                return last
        except (OSError, URLError, ValueError) as exc:
            last = {'network_error': str(exc)}
        time.sleep(.12)
    raise AssertionError(f'Expected {label}, last={last}')


def screenshot(name):
    binary = next((shutil.which(x) for x in
                   ('google-chrome', 'chromium', 'chromium-browser', 'chrome')
                   if shutil.which(x)), None)
    if not binary:
        raise RuntimeError('Chromium required for real dashboard screenshot; not available')
    target = EVIDENCE / name
    command = [binary, '--headless=new', '--no-sandbox', '--disable-gpu',
               '--disable-dev-shm-usage', '--hide-scrollbars', '--window-size=1480,1080',
               '--virtual-time-budget=1000', '--screenshot=' + str(target), BASE+'/']
    p = subprocess.run(command, capture_output=True, text=True, timeout=35)
    if p.returncode or not target.exists() or target.stat().st_size < 3000:
        raise RuntimeError(f'Real browser capture failed: {name}: {p.stderr[-350:]}')


def sql(query, params=()):
    with sqlite3.connect(DB, timeout=10) as db:
        return db.execute(query, params).fetchall()


def events():
    return sql('SELECT timestamp_utc,event,detail FROM monitor_events ORDER BY id')


def has_event(name):
    return any(event == name for _, event, _ in events())


def operator_action(name, detail, timestamp):
    with sqlite3.connect(DB, timeout=10) as db:
        db.execute('INSERT INTO monitor_events(timestamp_utc,event,detail) VALUES(?,?,?)',
                   (timestamp, name, detail))
        db.commit()


def create_report(stages):
    rows = [(t,e,d) for t,e,d in events() if e in REQUIRED]
    stamps = {event: ts for ts,event,_ in rows}
    timeline = []
    with (EVIDENCE/'timeline.csv').open('w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['time_utc','component','event','evidence','interpretation'])
        for time_, event, detail in rows:
            component = ('replay_worker' if event.startswith('SOURCE_')
                         else 'watchdog' if event in ('STALE_INPUT','INPUT_FAILED','HEALTH_RECOVERED')
                         else 'operator')
            interpretation = {
                'FAILURE_INJECTED': 'Operator creates source pause flag: controlled root cause',
                'SOURCE_PAUSED': 'First worker warning; cursor stopped advancing',
                'STALE_INPUT': 'Downstream stale-data symptom',
                'INPUT_FAILED': 'Downstream FAILED state after persistent outage',
                'RECOVERY_ACTION': 'Operator removes pause flag',
                'SOURCE_RESUMED': 'Worker resumes; duration and cursor recorded',
                'HEALTH_RECOVERED': 'New accepted arrival restores HEALTHY'
            }[event]
            writer.writerow([time_,component,event,detail,interpretation])
            timeline.append(f'| {time_} | {component} | {event} | {interpretation} |')
    normal, failed, recovered = (stages[k] for k in ('normal','failed','recovered'))
    body = f'''# EGN 321 — Assignment 7.2: Failure Investigation Report

**Failure tested:** stopping the replay input by creating `state/pause.flag`. All event times in the table are UTC. Original Module 6 source timestamps remain unchanged and are not treated as live arrival times.

## 1. System Before Failure

**Health:** {normal['health']}. **Latest accepted temperature:** {normal['current_value']} °C at replay arrival `{normal['latest_timestamp']}`. **Dashboard:** HTTP 200, real browser screenshot `normal_dashboard.png`. **Database:** source history {stages['archive_before']} rows across five sensors and SQLite `PRAGMA quick_check={stages['db_integrity']}`. **Alert active:** {normal['alert_active']}. Replay rows: {stages['replay_before']}.

## 2. Failure Introduced

At **{stamps.get('FAILURE_INJECTED')} UTC**, a controlled test operator created `state/pause.flag`, intentionally stopping replay input but not Flask or SQLite. Expected stale then failed health, observed exactly that. The operator action is recorded as `FAILURE_INJECTED` and supported by worker-generated `SOURCE_PAUSED`.

## 3. First Observable Symptom

**First source warning:** `SOURCE_PAUSED`, **{stamps.get('SOURCE_PAUSED')} UTC**; it includes the component, paused cursor and path. This is the first observed source failure. `STALE_INPUT` and `INPUT_FAILED` were later downstream **health symptoms**, not the root cause. The deliberate pause flag is the known root cause of this test.

## 4. Log Evidence

`application_logs.jsonl` contains actual machine-written structured logs; `application_events.csv` captures the SQLite audit table; `timeline.csv` identifies the important events. Screenshots are real browser captures of running Flask: normal, stale, failed and recovered. The source interruption logs now include `component`, `cursor`, `pause_file` and `elapsed_seconds` on resumption.

## 5. Timeline of Events

| Time (UTC) | Component | Event | Interpretation |
|---|---|---|---|
{chr(10).join(timeline)}

## 6. Possible Cause 1 — Replay Source Paused

**Supporting evidence:** operator-created pause file; worker `SOURCE_PAUSED` records source path and cursor; no new replay rows while paused; `SOURCE_RESUMED` after file removal. **Missing evidence:** OS audit identity of who would create a pause in a real deployment. **Verification test:** confirm flag exists and cursor stalls; remove only the flag without restarting Flask, then verify increased cursor, new accepted readings and healthy status. This test confirms the controlled pause explanation.

## 7. Possible Cause 2 — Worker Crash or SQLite Lock

**Supporting evidence:** lack of fresh arrivals also occurs after worker termination, thread stalls or database lockouts. **Missing evidence:** independent thread scheduling and database lock-wait instrumentation. **Verification test:** check worker/supervisor PIDs, `APPLICATION_ERROR` and `PROCESS_EXITED` logs, SQLite `PRAGMA quick_check`, and whether removal of only the flag resumes readings. Since Flask remained available and replay resumed without restarting it, this test contradicts crash/lock as the explanation of the observed classroom failure. A stale alert alone cannot distinguish the hypotheses.

## 8. Recovery Procedure

At **{stamps.get('RECOVERY_ACTION')} UTC**, the operator removed `state/pause.flag` without deleting any SQLite rows, resetting the cursor, or fabricating readings. The replay worker resumed and logged duration and cursor.

## 9. Verification of Recovery

`SOURCE_RESUMED` at **{stamps.get('SOURCE_RESUMED')} UTC** and `HEALTH_RECOVERED` at **{stamps.get('HEALTH_RECOVERED')} UTC**. Dashboard HTTP 200; `recovered_dashboard.png` shows **{recovered['health']}** and **{recovered['current_value']} °C**. Source-history rows before/after: **{stages['archive_before']} / {stages['archive_after']}**. Replay rows before/after: **{stages['replay_before']} / {stages['replay_after']}**. SQLite `quick_check` after: **{stages['db_integrity_after']}**. Alert remains **{recovered['alert_active']}**.

## 10. What the Logs Told Me

The logs identified operator action, first worker warning, stale/failed progression, source resume and restored input. Times and cursor data allow a repeatable timeline anchored to observable evidence rather than memory.

## 11. What the Logs Did Not Tell Me

Before the change, generic health events did not identify the **source component, pause-file path, or replay cursor**. The log still cannot identify an external operator or distinguish hardware disconnection from other stalls without additional operating-system instrumentation.

## 12. Improvement Made

Added **`SOURCE_PAUSED`** / **`SOURCE_RESUMED`** in JSONL and SQLite, plus machine-readable **component, source, cursor, pause file and elapsed seconds**. Added deterministic regression tests and an end-to-end investigation that fails rather than faking screenshots or omitting required evidence.

## 13. Remaining Limitations

Historical data is classroom replay, not a physical live sensor; original timestamps have unspecified timezone, while arrival timestamps use UTC. Failure was controlled by a pause flag; the scenario does not prove resilience against host outage, disk loss or database corruption. The Flask server remains a local test deployment. Previous Module 7.1 process-kill/restart evidence is separate; this assignment proves **input recovery without process restart**.
'''
    (EVIDENCE/'FAILURE_REPORT.md').write_text(body, encoding='utf-8')


def main():
    EVIDENCE.mkdir(exist_ok=True)
    DB.parent.mkdir(exist_ok=True)
    if DB.exists() or PAUSE.exists():
        raise RuntimeError('Failure-test DB or pause flag already exists; do not overwrite evidence')
    env = {**os.environ, 'MONITOR_DB':str(DB), 'MONITOR_LOG':str(LOG),
           'PORT':PORT, 'REPLAY_SECONDS':'.28',
           'STALE_DEGRADED_SECONDS':'1.6', 'STALE_FAILED_SECONDS':'3.8',
           'CLASSROOM_DEMO':'0', 'RESTART_DELAY_SECONDS':'.5',
           'PYTHONUNBUFFERED':'1'}
    supervisor = subprocess.Popen([sys.executable,'-u',str(ROOT/'supervisor.py')],
                                  cwd=ROOT, env=env,
                                  stdout=(EVIDENCE/'console.log').open('w'),
                                  stderr=subprocess.STDOUT, start_new_session=True)
    stages = {'scenario':'controlled replay pause', 'source':'Module 6 original CSV replay'}
    try:
        normal = wait_for('initial HEALTHY', lambda s:s.get('health')=='HEALTHY'
                          and s.get('counts',{}).get('replayed',0)>=3)
        stages['normal']=normal
        stages['archive_before']=sql('SELECT COUNT(*) FROM readings WHERE captured_at_utc IS NULL')[0][0]
        stages['replay_before']=normal['counts']['replayed']
        stages['db_integrity']=sql('PRAGMA quick_check')[0][0]
        assert stages['archive_before']==8780 and stages['db_integrity']=='ok'
        assert normal['alert_active'] is False and normal['current_value'] is not None
        assert fetch('/api/history?mode=archive&limit=5')['rows']
        screenshot('normal_dashboard.png')

        action_time=utc_now()
        PAUSE.touch(exist_ok=False)
        operator_action('FAILURE_INJECTED','component=operator action=create_pause_flag path='+str(PAUSE),action_time)
        wait_for('worker SOURCE_PAUSED',lambda s:has_event('SOURCE_PAUSED'))
        stale=wait_for('DEGRADED stale',lambda s:s.get('health')=='DEGRADED'
                       and 'stale' in s.get('reason','').lower(),timeout=18)
        stages['stale']=stale
        assert stale['current_value'] is None
        screenshot('stale_condition.png')
        failed=wait_for('FAILED',lambda s:s.get('health')=='FAILED',timeout=18)
        stages['failed']=failed
        assert failed['current_value'] is None
        screenshot('failed_condition.png')

        recovery_time=utc_now()
        PAUSE.unlink()
        operator_action('RECOVERY_ACTION','component=operator action=remove_pause_flag path='+str(PAUSE),recovery_time)
        resumed=wait_for('source resumed',lambda s:has_event('SOURCE_RESUMED'),timeout=18)
        recovered=wait_for('HEALTHY after resumption',lambda s:s.get('health')=='HEALTHY'
                           and s.get('counts',{}).get('replayed',0)>stages['replay_before'],timeout=18)
        stages['recovered']=recovered
        wait_for('HEALTH_RECOVERED event',lambda s:has_event('HEALTH_RECOVERED'),timeout=10)
        stages['archive_after']=sql('SELECT COUNT(*) FROM readings WHERE captured_at_utc IS NULL')[0][0]
        stages['replay_after']=recovered['counts']['replayed']
        stages['db_integrity_after']=sql('PRAGMA quick_check')[0][0]
        assert stages['archive_after']==stages['archive_before']==8780
        assert stages['db_integrity_after']=='ok' and recovered['alert_active'] is False
        screenshot('recovered_dashboard.png')
        seen={e for _,e,_ in events()}
        assert set(REQUIRED).issubset(seen),set(REQUIRED)-seen
        stages['required_events']=sorted(seen & set(REQUIRED))
        stages['verified']=True
        (EVIDENCE/'verification.json').write_text(json.dumps(stages,indent=2)+'\n',encoding='utf-8')
        create_report(stages)
        print(json.dumps({'result':'PASS','archive_rows':stages['archive_after'],
                          'replay_after':stages['replay_after'],
                          'required_events':stages['required_events']},indent=2))
    except Exception as exc:
        (EVIDENCE/'failure_error.json').write_text(json.dumps(
            {'error':repr(exc),'stages':stages},indent=2)+'\n',encoding='utf-8')
        raise
    finally:
        PAUSE.unlink(missing_ok=True)
        supervisor.terminate()
        try:supervisor.wait(timeout=7)
        except subprocess.TimeoutExpired:supervisor.kill();supervisor.wait()
        if LOG.exists():shutil.copy2(LOG,EVIDENCE/'application_logs.jsonl')
        if DB.exists():
            with sqlite3.connect(DB) as db:
                with (EVIDENCE/'application_events.csv').open('w',newline='',encoding='utf-8') as f:
                    out=csv.writer(f)
                    out.writerow(['timestamp_utc','event','detail'])
                    out.writerows(db.execute('SELECT timestamp_utc,event,detail FROM monitor_events ORDER BY id'))


if __name__=='__main__':main()
