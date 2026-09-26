"""
IID-SHEETS-LOG: Weekly archive script.
Downloads all rows from the Google Sheet to exports/sheets_backup_<date>.csv,
then clears the sheet so it stays lean.
The SheetsLogger auto-recreates the header on the next write.

Run manually or via Windows Task Scheduler (see scripts/archive_sheet.bat).
Credentials: credentials/service_account.json (gitignored).

    python scripts/archive_sheet.py                                   # main Sheet -> exports/
    python scripts/archive_sheet.py --config config_timeseries.yaml \\
        --out-dir exports/timeseries                                  # IID-WEEKLY-REPORT
"""

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_DIR = Path(__file__).parent.parent
SHEET_ID = "1Hg-r3cLuzGC8wAoYJFvyVlcDdLFVdDRcL77bVs5wpD8"
HEADER = ["timestamp", "session_id", "user_email", "course", "role", "content", "flagged_message", "model"]
EXPORTS_DIR = REPO_DIR / "exports"
CREDENTIALS = REPO_DIR / "credentials" / "service_account.json"


def sheet_id_from_config(config_path: Path) -> str:
    """IID-MULTI-DEPLOY: each deploy logs to the Sheet named by its config's sheets_log_id."""
    import yaml

    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    sheet_id = (cfg.get("sheets_log_id") or "").strip()
    if not sheet_id:
        raise SystemExit(f"ERROR: {config_path} has no sheets_log_id")
    return sheet_id


def archive(sheet_id: str = SHEET_ID, out_dir: Path = EXPORTS_DIR, clear: bool = True) -> tuple[Path | None, int]:
    """Download the Sheet to <out_dir>/sheets_backup_<ts>.csv; optionally remove what was archived.

    Returns (csv_path, n_data_rows); csv_path is None when the Sheet was empty.
    Rows are only removed after the CSV has been re-read and its row count matches.
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        raise SystemExit("ERROR: gspread / google-auth not installed. Run: pip install gspread google-auth")

    if not CREDENTIALS.exists():
        raise SystemExit(f"ERROR: credentials not found at {CREDENTIALS}")

    creds = Credentials.from_service_account_file(str(CREDENTIALS), scopes=["https://www.googleapis.com/auth/spreadsheets"])
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(sheet_id).sheet1

    raw_rows = ws.get_all_values()

    # get_all_values can return blank rows (e.g. [[]] after a clear) — drop them
    rows = [r for r in raw_rows if any(c.strip() for c in r)]
    if not rows:
        print("Sheet is already empty — nothing to archive.")
        return None, 0

    # Drop header row if present (we always write our own)
    first_is_header = rows[0][0] == "timestamp"
    data_rows = rows[1:] if first_is_header else rows
    if not data_rows:
        print("Sheet holds only the header — nothing to archive.")
        return None, 0

    out_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
    outfile = out_dir / f"sheets_backup_{date_str}.csv"

    with outfile.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        writer.writerows(data_rows)

    # Verify the backup before deleting anything from the Sheet.
    with outfile.open(newline="", encoding="utf-8") as f:
        n_written = sum(1 for _ in csv.reader(f)) - 1
    if n_written != len(data_rows):
        raise SystemExit(f"ERROR: backup has {n_written} rows, expected {len(data_rows)} — Sheet NOT cleared")

    print(f"Archived {len(data_rows)} rows -> {outfile}")

    if not clear:
        print("--keep: Sheet left untouched.")
        return outfile, len(data_rows)

    # A student may have chatted between download and clear. Only a Sheet that is
    # unchanged is cleared wholesale; otherwise just the archived rows are deleted.
    now_len = len(ws.get_all_values())
    if now_len == len(raw_rows):
        ws.clear()
        print("Sheet cleared. Header will be recreated on next student interaction.")
    else:
        start = 2 if first_is_header else 1  # keep the header row
        ws.delete_rows(start, len(raw_rows))
        print(f"Sheet grew during archive ({len(raw_rows)} -> {now_len} rows); deleted only archived rows {start}-{len(raw_rows)}.")

    return outfile, len(data_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, help="read sheets_log_id from this config (default: main Sheet)")
    parser.add_argument("--out-dir", type=Path, default=EXPORTS_DIR, help="where to write the CSV (default: exports/)")
    parser.add_argument("--keep", action="store_true", help="download only, do not clear the Sheet")
    args = parser.parse_args()

    sheet_id = sheet_id_from_config(args.config) if args.config else SHEET_ID
    try:
        archive(sheet_id, args.out_dir, clear=not args.keep)
    except SystemExit as e:
        print(e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
