@echo off
REM IID-WEEKLY-REPORT: weekly Timeseries chat report by e-mail (Wednesdays).
REM Registered in Task Scheduler as "lectos-timeseries-weekly" with "run as soon as possible
REM after a missed start" - see CLAUDE.md. Runs at most once per ISO week (state.json).

cd /d "C:\Users\Schmidt\Dropbox\R packages\teachbot"
if not exist exports\timeseries mkdir exports\timeseries
set PYTHONIOENCODING=utf-8
.venv\Scripts\python scripts\weekly_report.py >> exports\timeseries\weekly_log.txt 2>&1
