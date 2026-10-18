# EGN 321 — Assignment 7.2: Failure Investigation Report

**Failure tested:** stopping the replay input by creating `state/pause.flag`. All event times in the table are UTC. Original Module 6 source timestamps remain unchanged and are not treated as live arrival times.

## 1. System Before Failure

**Health:** HEALTHY. **Latest accepted temperature:** 22.14 °C at replay arrival `2026-10-18T17:49:08.230+00:00`. **Dashboard:** HTTP 200, real browser screenshot `normal_dashboard.png`. **Database:** source history 8780 rows across five sensors and SQLite `PRAGMA quick_check=ok`. **Alert active:** False. Replay rows: 3.

## 2. Failure Introduced

At **2026-10-18T17:49:15.853+00:00 UTC**, a controlled test operator created `state/pause.flag`, intentionally stopping replay input but not Flask or SQLite. Expected stale then failed health, observed exactly that. The operator action is recorded as `FAILURE_INJECTED` and supported by worker-generated `SOURCE_PAUSED`.

## 3. First Observable Symptom

**First source warning:** `SOURCE_PAUSED`, **2026-10-18T17:49:16.132+00:00 UTC**; it includes the component, paused cursor and path. This is the first observed source failure. `STALE_INPUT` and `INPUT_FAILED` were later downstream **health symptoms**, not the root cause. The deliberate pause flag is the known root cause of this test.

## 4. Log Evidence

`application_logs.jsonl` contains actual machine-written structured logs; `application_events.csv` captures the SQLite audit table; `timeline.csv` identifies the important events. Screenshots are real browser captures of running Flask: normal, stale, failed and recovered. The source interruption logs now include `component`, `cursor`, `pause_file` and `elapsed_seconds` on resumption.

## 5. Timeline of Events

| Time (UTC) | Component | Event | Interpretation |
|---|---|---|---|
| 2026-10-18T17:49:15.853+00:00 | operator | FAILURE_INJECTED | Operator creates source pause flag: controlled root cause |
| 2026-10-18T17:49:16.132+00:00 | replay_worker | SOURCE_PAUSED | First worker warning; cursor stopped advancing |
| 2026-10-18T17:49:18.884+00:00 | watchdog | STALE_INPUT | Downstream stale-data symptom |
| 2026-10-18T17:49:24.501+00:00 | watchdog | INPUT_FAILED | Downstream FAILED state after persistent outage |
| 2026-10-18T17:49:25.372+00:00 | operator | RECOVERY_ACTION | Operator removes pause flag |
| 2026-10-18T17:49:25.545+00:00 | replay_worker | SOURCE_RESUMED | Worker resumes; duration and cursor recorded |
| 2026-10-18T17:49:25.557+00:00 | watchdog | HEALTH_RECOVERED | New accepted arrival restores HEALTHY |

## 6. Possible Cause 1 — Replay Source Paused

**Supporting evidence:** operator-created pause file; worker `SOURCE_PAUSED` records source path and cursor; no new replay rows while paused; `SOURCE_RESUMED` after file removal. **Missing evidence:** OS audit identity of who would create a pause in a real deployment. **Verification test:** confirm flag exists and cursor stalls; remove only the flag without restarting Flask, then verify increased cursor, new accepted readings and healthy status. This test confirms the controlled pause explanation.

## 7. Possible Cause 2 — Worker Crash or SQLite Lock

**Supporting evidence:** lack of fresh arrivals also occurs after worker termination, thread stalls or database lockouts. **Missing evidence:** independent thread scheduling and database lock-wait instrumentation. **Verification test:** check worker/supervisor PIDs, `APPLICATION_ERROR` and `PROCESS_EXITED` logs, SQLite `PRAGMA quick_check`, and whether removal of only the flag resumes readings. Since Flask remained available and replay resumed without restarting it, this test contradicts crash/lock as the explanation of the observed classroom failure. A stale alert alone cannot distinguish the hypotheses.

## 8. Recovery Procedure

At **2026-10-18T17:49:25.372+00:00 UTC**, the operator removed `state/pause.flag` without deleting any SQLite rows, resetting the cursor, or fabricating readings. The replay worker resumed and logged duration and cursor.

## 9. Verification of Recovery

`SOURCE_RESUMED` at **2026-10-18T17:49:25.545+00:00 UTC** and `HEALTH_RECOVERED` at **2026-10-18T17:49:25.557+00:00 UTC**. Dashboard HTTP 200; `recovered_dashboard.png` shows **HEALTHY** and **22.24 °C**. Source-history rows before/after: **8780 / 8780**. Replay rows before/after: **3 / 31**. SQLite `quick_check` after: **ok**. Alert remains **False**.

## 10. What the Logs Told Me

The logs identified operator action, first worker warning, stale/failed progression, source resume and restored input. Times and cursor data allow a repeatable timeline anchored to observable evidence rather than memory.

## 11. What the Logs Did Not Tell Me

Before the change, generic health events did not identify the **source component, pause-file path, or replay cursor**. The log still cannot identify an external operator or distinguish hardware disconnection from other stalls without additional operating-system instrumentation.

## 12. Improvement Made

Added **`SOURCE_PAUSED`** / **`SOURCE_RESUMED`** in JSONL and SQLite, plus machine-readable **component, source, cursor, pause file and elapsed seconds**. Added deterministic regression tests and an end-to-end investigation that fails rather than faking screenshots or omitting required evidence.

## 13. Remaining Limitations

Historical data is classroom replay, not a physical live sensor; original timestamps have unspecified timezone, while arrival timestamps use UTC. Failure was controlled by a pause flag; the scenario does not prove resilience against host outage, disk loss or database corruption. The Flask server remains a local test deployment. Previous Module 7.1 process-kill/restart evidence is separate; this assignment proves **input recovery without process restart**.
