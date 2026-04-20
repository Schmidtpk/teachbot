@echo off
REM Weekly Google Sheet archive — IID-SHEETS-LOG
REM Register in Windows Task Scheduler to run every Sunday.
REM Setup: schtasks /create /tn "teachbot-archive" /tr "\"C:\Users\Schmidt\Dropbox\R packages\teachbot\scripts\archive_sheet.bat\"" /sc weekly /d SUN /st 08:00

cd /d "C:\Users\Schmidt\Dropbox\R packages\teachbot"
.venv\Scripts\python scripts\archive_sheet.py >> exports\archive_log.txt 2>&1
