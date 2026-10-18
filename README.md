# EGN 321 · Module 7, Assignment 7.2
## Failure Report: Diagnose, Recover, and Improve the System

**Submission repository:** https://github.com/Barquito0/EGN-321-Module-7_2  
**Earlier, working system:** https://github.com/Barquito0/Module-7_1  
**Instructor reference:** https://github.com/ivansuarez-AU/EGN321_Module7_Assignment7_2

This project preserves the existing Module 7.1 Flask / SQLite unattended monitoring application and investigates **one controlled source failure**: deliberately stopping the replay worker by creating `state/pause.flag`. The original Module 6 SQLite history remains intact, and a dedicated test database is used for the investigation. Normal readings are never fabricated to bridge the interruption.

### Investigation process

```text
Normal accepted replay reading, HEALTHY
    ↓
Operator creates state/pause.flag (recorded as FAILURE_INJECTED)
    ↓
Worker reports SOURCE_PAUSED — first observable source warning
    ↓
Freshness watchdog reports STALE_INPUT → DEGRADED
    ↓
Continued interruption reports INPUT_FAILED → FAILED
    ↓
Review machine-written JSONL and SQLite event sequence
    ↓
Test competing hypotheses (source pause versus worker/DB failure)
    ↓
Operator removes only pause.flag (RECOVERY_ACTION)
    ↓
SOURCE_RESUMED and new accepted reading; HEALTH_RECOVERED → HEALTHY
```

### How to run

Use Python 3.11 or newer, preferably in an isolated environment:

```bash
python -m pip install -r requirements.txt
python -m scripts.seed_history
python -m pytest -q
python supervisor.py
```

Then visit **http://127.0.0.1:5000**. The supervisor restarts the Flask process after unexpected exit. The systemd example at `scripts/monitor7.service.example` supports automatic boot on a configured Linux machine, but it is a *sample* rather than evidence that systemd is currently installed or enabled on a student's computer. Do not expose the Flask development server publicly.

### Reproduce the 7.2 controlled failure

On Linux with Chrome/Chromium available, from a clean clone:

```bash
python -m scripts.seed_history
python scripts/failure_investigation.py
```

The script launches the real Flask application through its supervisor on local port **5139**, uses a **separate** working SQLite DB (`state/failure_monitor.db`), collects genuine browser screenshots, pauses the source, waits for the watchdog's stale and failed states, removes the flag, then verifies the database and dashboard after recovery. It **fails loudly** rather than manufacturing screenshots or calling an unverified attempt a success. If a dedicated test database or pause flag already exists, it refuses to overwrite earlier evidence; archive/rename that test database manually to rerun.

This investigation **does not kill Flask**. The chosen failure is a replay-source stop; process-kill recovery was separately verified in [Module 7.1](https://github.com/Barquito0/Module-7_1). The source-stop test shows recovery without a process restart.

### Data source and history

- Original source: instructor-supplied Module 6 virtual-sensor dataset, `data/module6_sample_sensor_history.csv`, **1,756 timestamped rows** covering five sensors; source timestamps are preserved and their timezone was unspecified.
- Reconstructed seed: `data/module6_sensor_history.db` is generated without changing the original timestamps, with **8,780 readings** (1,756 × 5). `scripts/seed_history.py` is the deterministic seed generator.
- Working DB: `state/monitor.db` for normal operation, or `state/failure_monitor.db` for the investigation. Existing runtime history is **not deleted on restart**.
- Original source expected interval: **60 seconds**. The Module 7 replay arrives about every **2 seconds** in ordinary operation, or **0.28 seconds for the accelerated isolated incident test**. Arrival timestamps are separate UTC timestamps; original source observations are not relabeled as contemporary field measurements.
- Known Module 6 missing intervals: 25 and 20 absent one-minute slots. Neither the original dataset nor SQLite is padded with guessed measurements.

### Threshold alerts, watchdog and health

- Sensor: **temperature**, degrees Celsius (°C).
- Validation: missing/non-numeric/non-finite/source-non-OK/outside **0–50°C** readings rejected; raw and accepted values are stored separately.
- Alert threshold: **3 consecutive accepted readings at least 30.0°C** activate an alert; **2 consecutive readings at or below 28.5°C** clear it. Threshold persistence and hysteresis control noise. Alert states persist across restart in SQLite.
- Default replay freshness: **DEGRADED** after 8 seconds without a new reading; **FAILED** after 18 seconds. The investigation temporarily sets **2.8 seconds** and **8.5 seconds**, respectively, to test in a reasonable period.
- States: **RECOVERING**, **HEALTHY**, **DEGRADED**, **FAILED**. When data are stale or rejected, the dashboard does not claim an old value is current.

### Log files and the change made for 7.2

Existing logs: rotating JSONL `logs/monitor.jsonl`, backed by SQLite `monitor_events`. The investigation's independent log is `logs/failure_monitor.jsonl` and its output is copied to `evidence/application_logs.jsonl`.

**Improvement:** before this investigation, generic health events told us only that arrivals were stale or missing. `src/monitor.py` now produces **`SOURCE_PAUSED` and `SOURCE_RESUMED`** with the exact worker component, cursor, pause path, source CSV path and elapsed paused duration. `src/eventlog.py` also emits these as structured fields rather than only as a free-text message. SQLite records both transitions. Those fields let the investigator identify the **earliest source warning** and distinguish a known source pause from downstream stale/failed symptoms.

### Evidence and report

After the successful GitHub Actions workflow, `evidence/` contains:

| Required evidence | Path |
|---|---|
| Complete 13-section report | `evidence/FAILURE_REPORT.md` |
| Precise causal timeline | `evidence/timeline.csv` |
| Original JSONL logs | `evidence/application_logs.jsonl` |
| SQLite audit events | `evidence/application_events.csv` |
| Normal dashboard and reading | `evidence/normal_dashboard.png` |
| Stale / DEGRADED state | `evidence/stale_condition.png` |
| Failed input / FAILED state | `evidence/failed_condition.png` |
| Recovered HEALTHY dashboard | `evidence/recovered_dashboard.png` |
| Machine-checked verification | `evidence/verification.json` |
| Full test output | GitHub Actions workflow run |

The report follows exactly the 13 headings required by the assignment, states the first observed error, distinguishes confirmed root cause from downstream effects, evaluates **two plausible causes** with evidence gaps and deterministic tests, and notes what the logs did not establish.

### Tests and CI

```bash
python -m pytest -q
```

`tests/test_failure_diagnostics.py` verifies structured context in JSONL, a real paused and resumed worker, an unchanging cursor while paused, and preservation of the source SQLite archive. Existing Module 7.1 tests continue checking health states, alert persistence and recovery. GitHub Actions starts the real service with a supervisor and a browser, carries out the failure scenario, verifies log events and data persistence, then commits **real-generated** screenshots and report. The workflow itself is the executable recovery test, not an unsupported written claim.

### Human intervention / limitations

The replay pause is recoverable by removing the flag; the Flask child can recover from process exit through the supervisor. Database corruption, disk exhaustion, host outage, permanent sensor failure, invalid permissions and crashes of the supervisor/host still need a human/operator or separate platform service. The experiment is a classroom simulation, not a permanently hosted service or real hardware sensor. Timestamp source and evidence provenance are explicitly separated. The exact external person who sets a pause flag cannot be inferred from the app logs without OS-level audit information.

### AI use

See `AI_LOG.md`; AI was used for code drafting, hypothesis comparison and test planning, never for inventing readings, incident logs or screenshots. Verification relies on deterministic code, actual SQLite contents, HTTP responses and genuine browser images.