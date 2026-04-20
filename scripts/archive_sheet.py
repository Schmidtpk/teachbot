"""
IID-SHEETS-LOG: Weekly archive script.
Downloads all rows from the Google Sheet to exports/sheets_backup_<date>.csv,
then clears the sheet (including any header) so it stays lean.
The SheetsLogger auto-recreates the header on the next write.

Run manually or via Windows Task Scheduler (see scripts/archive_sheet.bat).
Credentials: credentials/service_account.json (gitignored).
"""

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SHEET_ID = "1Hg-r3cLuzGC8wAoYJFvyVlcDdLFVdDRcL77bVs5wpD8"
HEADER = ["timestamp", "session_id", "user_email", "role", "content", "flagged_message"]
EXPORTS_DIR = Path(__file__).parent.parent / "exports"
CREDENTIALS = Path(__file__).parent.parent / "credentials" / "service_account.json"


def main() -> None:
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("ERROR: gspread / google-auth not installed. Run: pip install gspread google-auth", file=sys.stderr)
        sys.exit(1)

    if not CREDENTIALS.exists():
        print(f"ERROR: credentials not found at {CREDENTIALS}", file=sys.stderr)
        sys.exit(1)

    creds = Credentials.from_service_account_file(str(CREDENTIALS), scopes=["https://www.googleapis.com/auth/spreadsheets"])
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SHEET_ID).sheet1

    rows = ws.get_all_values()

    if not rows:
        print("Sheet is already empty — nothing to archive.")
        return

    # Drop header row if present (we always write our own)
    first_is_header = rows[0][0] == "timestamp"
    data_rows = rows[1:] if first_is_header else rows

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
    outfile = EXPORTS_DIR / f"sheets_backup_{date_str}.csv"

    with outfile.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        writer.writerows(data_rows)

    print(f"Archived {len(data_rows)} rows -> {outfile}")

    ws.clear()
    print("Sheet cleared. Header will be recreated on next student interaction.")


if __name__ == "__main__":
    main()
