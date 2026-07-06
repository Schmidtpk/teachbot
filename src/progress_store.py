"""
IID-LEARN-GOALS, IID-AUTH-BASIC, IID-SHEETS-LOG, SID-PRIVACY-DATA
Per-student persistence of completed learning goals for the learning-goals practice mode.

Keyed by (user_email, course_name). Backends, in priority order:
  1. Google Sheet tab `progress` in the configured `sheets_log_id` sheet — survives Railway
     redeploys (the only durable store; users.yaml and local files are wiped on redeploy).
  2. Local JSON `progress/<email>.json` — dev fallback when Sheets is disabled but an email exists.
  3. In-session only — when no email is available (auth disabled); nothing is persisted.

Reuses the shared service-account client from src/chat_logger.gspread_client().
"""

import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.chat_logger import gspread_client

_PROGRESS_WS_TITLE = "progress"
_PROGRESS_HEADER = ["timestamp", "user_email", "course", "goal_id"]


def _safe_filename(email: str) -> str:
    """Make an email safe to use as a filename for the local-JSON fallback."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", email)


class ProgressStore:
    """IID-LEARN-GOALS: Track which learning goals a student has completed."""

    def __init__(
        self,
        sheet_id: str,
        user_email: Optional[str],
        course_name: str,
        progress_dir: str | Path = "progress",
    ) -> None:
        self._course_name = course_name
        self._user_email = user_email  # None when auth is disabled
        # Backend selection
        if user_email and sheet_id:
            self._backend = "sheets"
            self._sheet_id = sheet_id
            self._ws = None  # lazily initialised
        elif user_email:
            self._backend = "local"
            self._dir = Path(progress_dir)
            self._dir.mkdir(parents=True, exist_ok=True)
            self._file = self._dir / f"{_safe_filename(user_email)}.json"
        else:
            self._backend = "memory"
            print(
                "[ProgressStore] WARNING: no user_email (auth disabled) — learning-goals "
                "progress will not persist across sessions.",
                file=sys.stderr,
            )

    # -- Google Sheets backend -------------------------------------------------

    def _get_ws(self):
        if self._ws is not None:
            return self._ws
        gc = gspread_client()
        sh = gc.open_by_key(self._sheet_id)
        try:
            ws = sh.worksheet(_PROGRESS_WS_TITLE)
        except Exception:
            ws = sh.add_worksheet(title=_PROGRESS_WS_TITLE, rows=1000, cols=len(_PROGRESS_HEADER))
            ws.append_row(_PROGRESS_HEADER, value_input_option="RAW")
        self._ws = ws
        return ws

    def _read_sheets(self) -> set[str]:
        try:
            ws = self._get_ws()
            rows = ws.get_all_values()
        except Exception as exc:
            print(f"[ProgressStore] WARNING: failed to read progress from Sheets: {exc}", file=sys.stderr)
            return set()
        done: set[str] = set()
        for row in rows[1:]:  # skip header
            # columns: timestamp, user_email, course, goal_id
            if len(row) >= 4 and row[1] == self._user_email and row[2] == self._course_name:
                done.add(row[3])
        return done

    def _append_sheets(self, goal_id: str) -> None:
        try:
            ws = self._get_ws()
            if not ws.row_values(1):
                ws.append_row(_PROGRESS_HEADER, value_input_option="RAW")
            ts = datetime.now(timezone.utc).isoformat()
            ws.append_row(
                [ts, self._user_email or "", self._course_name, goal_id],
                value_input_option="RAW",
                insert_data_option="INSERT_ROWS",
            )
        except Exception as exc:
            print(f"[ProgressStore] WARNING: failed to write progress to Sheets: {exc}", file=sys.stderr)

    # -- Local JSON backend ----------------------------------------------------

    def _read_local(self) -> set[str]:
        if not self._file.exists():
            return set()
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
            return set(data.get(self._course_name, []))
        except (json.JSONDecodeError, OSError):
            return set()

    def _append_local(self, goal_id: str) -> None:
        data: dict = {}
        if self._file.exists():
            try:
                data = json.loads(self._file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = {}
        done = set(data.get(self._course_name, []))
        done.add(goal_id)
        data[self._course_name] = sorted(done)
        self._file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # -- Public API ------------------------------------------------------------

    async def completed_goal_ids(self) -> set[str]:
        """IID-LEARN-GOALS: Goal ids this student has already completed for this course.

        Runs the (blocking) backend read in a thread-pool executor so it never blocks the
        async on_chat_start handler. In-memory backend always returns an empty set.
        """
        if self._backend == "memory":
            return set()
        loop = asyncio.get_event_loop()
        reader = self._read_sheets if self._backend == "sheets" else self._read_local
        return await loop.run_in_executor(None, reader)

    def mark_done(self, goal_id: str) -> None:
        """IID-LEARN-GOALS: Persist that the student completed `goal_id` (fire-and-forget)."""
        if self._backend == "memory":
            return
        loop = asyncio.get_event_loop()
        writer = self._append_sheets if self._backend == "sheets" else self._append_local
        loop.run_in_executor(None, writer, goal_id)
