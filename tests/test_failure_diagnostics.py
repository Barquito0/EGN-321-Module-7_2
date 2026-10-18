"""Deterministic regression evidence for the logging/design improvement."""
import json
import threading
import time
from datetime import datetime, timedelta

from src.eventlog import get_logger, log_event
from src.monitor import run_worker
from src.storage import initialize, meta_get
from src.health import health_snapshot


def until(predicate, timeout=8):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(.035)
    return False


def test_structured_log_includes_source_diagnostic_fields(tmp_path):
    logfile = tmp_path / 'incident.jsonl'
    logger = get_logger(logfile, name='test.module7_2.diagnostics')
    log_event(logger, 'SOURCE_PAUSED', 'test pause event', 'warning',
              component='replay_worker', cursor=12, pause_file='pause.flag',source='source.csv')
    for handler in logger.handlers:
        handler.flush()
    payload = json.loads(logfile.read_text(encoding='utf-8').splitlines()[-1])
    assert payload['event'] == 'SOURCE_PAUSED'
    assert payload['component'] == 'replay_worker'
    assert payload['cursor'] == 12
    assert payload['pause_file'] == 'pause.flag'
    assert payload['source'] == 'source.csv'


def test_paused_source_and_recovery_preserve_sqlite_and_cursor(tmp_path, monkeypatch):
    from src import monitor
    flag = tmp_path / 'pause.flag'
    monkeypatch.setattr(monitor, 'PAUSE_FILE', flag)
    dataset = tmp_path / 'sensor.csv'
    dataset.write_text(
        'sample_number,timestamp,temperature_c,temperature_status\n'
        '1,2026-10-01T08:00:00,22.0,OK\n'
        '2,2026-10-01T08:01:00,22.1,OK\n'
        '3,2026-10-01T08:02:00,22.2,OK\n', encoding='utf-8')
    db = tmp_path / 'monitor.db'
    stop = threading.Event()
    error = []
    with initialize(db) as conn:
        initial = conn.execute('SELECT COUNT(*) FROM readings').fetchone()[0]
        assert initial == 8780

    def worker():
        try:
            run_worker(stop, db_path=db, csv_path=dataset, interval=.08, demo=False)
        except Exception as exc:
            error.append(exc)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    try:
        def cursor():
            with initialize(db) as c:
                return meta_get(c,'cursor',0)
        def event_count(e):
            with initialize(db) as c:
                return c.execute('SELECT COUNT(*) FROM monitor_events WHERE event=?',(e,)).fetchone()[0]
        assert until(lambda:cursor()>=2)
        flag.touch()
        assert until(lambda:event_count('SOURCE_PAUSED')==1)
        paused_cursor = cursor()
        time.sleep(.25)
        assert cursor() == paused_cursor, 'Cursor advanced while source was paused'
        with initialize(db) as conn:
            latest = conn.execute("SELECT captured_at_utc FROM readings WHERE sensor='temperature' AND captured_at_utc IS NOT NULL ORDER BY timestamp DESC LIMIT 1").fetchone()[0]
            snap = health_snapshot(conn, now=datetime.fromisoformat(latest)+timedelta(seconds=20))
            assert snap['health'] == 'FAILED' and snap['current_value'] is None
        flag.unlink()
        assert until(lambda:event_count('SOURCE_RESUMED')==1)
        assert until(lambda:cursor()>paused_cursor)
        with initialize(db) as conn:
            assert conn.execute('SELECT COUNT(*) FROM readings WHERE captured_at_utc IS NULL').fetchone()[0] == initial
            assert conn.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
        assert not error, error
    finally:
        flag.unlink(missing_ok=True)
        stop.set()
        t.join(timeout=3)
