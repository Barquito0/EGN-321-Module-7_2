# Deliverables checklist

- [x] Inherited Module 7.1 Flask application source, validation, SQLite and supervisor.
- [x] Controlled failure injection/recovery script (`scripts/failure_investigation.py`).
- [x] Improved structured source-pause logging (`src/eventlog.py`, `src/monitor.py`).
- [x] Regressions for logger fields, paused cursor, recovery, SQLite integrity (`tests/test_failure_diagnostics.py`).
- [x] README, AI log, repeatable GitHub workflow.
- [x] CI-generated `evidence/FAILURE_REPORT.md` with all 13 required headings; the workflow must pass to check.
- [x] CI-generated `evidence/timeline.csv` and original machine logs; workflow must pass to check.
- [x] Four genuine dashboard screenshots of normal, stale, failed and recovered states; workflow must pass to check.
- [x] `evidence/verification.json` asserting DB persistence and healthy recovery; workflow must pass to check.

The GitHub Actions job verified these items before committing evidence. A failed run cannot be presented as successful recovery.
## Verified GitHub Actions incident run

- [x] [Run 39151149764](https://github.com/Barquito0/EGN-321-Module-7_2/actions/runs/39151149764) completed successfully.
- [x] HEALTHY → DEGRADED → FAILED → HEALTHY; recorded source pause and resume.
- [x] 8,780 original archive rows before and after; SQLite `PRAGMA quick_check = ok`.
- [x] Four real dashboard PNGs and 13-section failure report committed to `evidence/`.
