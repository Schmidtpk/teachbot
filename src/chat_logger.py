"""
IID-CHAT-LOG, IID-SHEETS-LOG, IID-AUTH-BASIC, SID-PRIVACY-DATA
Write each chat turn to a per-session JSONL file in the logs/ directory,
and optionally to a Google Sheet for persistent cross-deploy storage.
When IID-AUTH-BASIC is active, user_email is included in each log entry.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class ChatLogger:
    """Append chat turns to logs/<session_id>.jsonl (IID-CHAT-LOG)."""

    def __init__(self, logs_dir: str | Path, session_id: str, user_email: Optional[str] = None) -> None:
        logs_path = Path(logs_dir)
        logs_path.mkdir(parents=True, exist_ok=True)
        self._file = logs_path / f"{session_id}.jsonl"
        self._user_email = user_email  # IID-AUTH-BASIC: None when auth is disabled

    def log(self, role: str, content: str) -> None:
        """Append one turn. role is 'user' or 'assistant'."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "role": role,
            "content": content,
        }
        if self._user_email:  # IID-AUTH-BASIC: include email when auth is active
            entry["user_email"] = self._user_email
        with self._file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


# IID-SHEETS-LOG: persistent cross-deploy logging via Google Sheets service account.
_SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_HEADER_ROW = ["timestamp", "session_id", "user_email", "role", "content"]


class SheetsLogger:
    """Append chat turns as rows to a Google Sheet (IID-SHEETS-LOG, IID-AUTH-BASIC, SID-PRIVACY-DATA).

    Authentication uses a service account whose JSON key is read from the
    GOOGLE_SERVICE_ACCOUNT_JSON environment variable (set as a Railway secret).
    Writes are dispatched to a thread-pool executor so they never block the
    async Chainlit message handler.
    """

    def __init__(self, sheet_id: str, session_id: str, user_email: Optional[str] = None) -> None:
        self._sheet_id = sheet_id
        self._session_id = session_id
        self._user_email = user_email  # IID-AUTH-BASIC: None when auth is disabled
        self._ws = None  # lazily initialised on first write

    def _get_ws(self):
        """Return the first worksheet, opening the sheet if needed."""
        if self._ws is not None:
            return self._ws
        import gspread
        from google.oauth2.service_account import Credentials

        raw = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
        info = json.loads(raw)
        creds = Credentials.from_service_account_info(info, scopes=_SHEETS_SCOPES)
        gc = gspread.authorize(creds)
        self._ws = gc.open_by_key(self._sheet_id).sheet1
        return self._ws

    def _append(self, role: str, content: str) -> None:
        """Blocking write called from a thread-pool executor."""
        try:
            ws = self._get_ws()
            # Auto-add header row if the sheet is empty
            if not ws.row_values(1):
                ws.append_row(_HEADER_ROW, value_input_option="RAW")
            ts = datetime.now(timezone.utc).isoformat()
            ws.append_row(
                [ts, self._session_id, self._user_email or "", role, content],
                value_input_option="RAW",
                insert_data_option="INSERT_ROWS",
            )
        except Exception as exc:
            print(f"[SheetsLogger] WARNING: failed to write to Sheets: {exc}", file=sys.stderr)

    def log(self, role: str, content: str) -> None:
        """Fire-and-forget: dispatches write to executor so it doesn't block streaming."""
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, self._append, role, content)
