# Deliverables checklist

- [x] Inherited Module 7.1 Flask application source, validation, SQLite and supervisor.
- [x] Controlled failure injection/recovery script (`scripts/failure_investigation.py`).
- [x] Improved structured source-pause logging (`src/eventlog.py`, `src/monitor.py`).
- [x] Regressions for logger fields, paused cursor, recovery, SQLite integrity (`tests/test_failure_diagnostics.py`).
- [x] README, AI log, repeatable GitHub workflow.
- [ ] CI-generated `evidence/FAILURE_REPORT.md` with all 13 required headings; the workflow must pass to check.
- [ ] CI-generated `evidence/timeline.csv` and original machine logs; workflow must pass to check.
- [ ] Four genuine dashboard screenshots of normal, stale, failed and recovered states; workflow must pass to check.
- [ ] `evidence/verification.json` asserting DB persistence and healthy recovery; workflow must pass to check.

The GitHub Actions job checks the unchecked items before making its evidence commit. A failure produces an Actions error instead of a false claim of completion.