# AI Use Log — Module 7.2

AI assistance was used to review the instructor's required investigation process, inspect the existing Module 7.1 application, select the source-pause scenario, plan competing hypotheses, draft the logging improvement, implement the deterministic failure exercise and tests, and organize the README/report.

AI is **not** used to synthesize or edit observed sensor measurements, invent timestamps, claim unobserved events or generate fake browser screenshots. The controlled operator action is explicitly labeled. The report and screenshots are generated only after a real supervised Flask process, SQLite event logs, watchdog state changes and a successful source-recovery test meet deterministic assertions.

Plausible alternatives (worker crash/SQLite blockage) are hypotheses, not declared causal facts; each has a verification test. All root-cause statements in the report are limited to the controlled source-pause experiment. The student should review the result and be able to explain the event order and the additional log fields.