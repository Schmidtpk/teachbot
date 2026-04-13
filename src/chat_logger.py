"""
IID-CHAT-LOG, SID-PRIVACY-DATA
Write each chat turn to a per-session JSONL file in the logs/ directory.
No PII is stored: only session UUID, timestamp, role, and message content.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


class ChatLogger:
    """Append chat turns to logs/<session_id>.jsonl (IID-CHAT-LOG)."""

    def __init__(self, logs_dir: str | Path, session_id: str) -> None:
        logs_path = Path(logs_dir)
        logs_path.mkdir(parents=True, exist_ok=True)
        self._file = logs_path / f"{session_id}.jsonl"

    def log(self, role: str, content: str) -> None:
        """Append one turn. role is 'user' or 'assistant'. SID-PRIVACY-DATA: no PII."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "role": role,
            "content": content,
        }
        with self._file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
