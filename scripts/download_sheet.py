"""
IID-SHEETS-LOG: Non-destructive download.
Downloads all rows from the Google Sheet to exports/sheets_backup_<date>.csv.
Unlike archive_sheet.py, this does NOT clear the sheet.

    python scripts/download_sheet.py
"""

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

SHEET_ID = "1Hg-r3cLuzGC8wAoYJFvyVlcDdLFVdDRcL77bVs5wpD8"
HEADER = ["timestamp", "session_id", "user_email", "course", "role", "content", "flagged_message", "model"]
EXPORTS_DIR = Path(__file__).parent.parent / "exports"
CREDENTIALS = Path(__file__).parent.parent / "credentials" / "service_account.json"


def main() -> None:
    import gspread
    from google.oauth2.service_account import Credentials

    if not CREDENTIALS.exists():
        print(f"ERROR: credentials not found at {CREDENTIALS}", file=sys.stderr)
        sys.exit(1)

    creds = Credentials.from_service_account_file(str(CREDENTIALS), scopes=["https://www.googleapis.com/auth/spreadsheets"])
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SHEET_ID).sheet1

    rows = ws.get_all_values()
    if not rows:
        print("Sheet is empty — nothing to download.")
        return

    first_is_header = rows[0][0] == "timestamp"
    data_rows = rows[1:] if first_is_header else rows

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
    outfile = EXPORTS_DIR / f"sheets_backup_{date_str}.csv"

    with outfile.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        writer.writerows(data_rows)

    print(f"Downloaded {len(data_rows)} rows -> {outfile} (sheet NOT cleared)")


if __name__ == "__main__":
    main()
