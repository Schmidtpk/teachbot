"""
IID-AUTH-BASIC
Email-gated authentication helpers for teachbot.

Flow:
  - Educator configures allowed_domains / allowed_emails in config.yaml (auth: section).
  - Students use the Chainlit login form (username = email, password of their choice).
  - First successful login with an allowed email = automatic registration.
  - Subsequent logins verify the stored bcrypt hash.
  - If allowed_domains and allowed_emails are both empty, auth is disabled (public mode).

User accounts are stored in users.yaml (gitignored, created at runtime).
Password reset: educator removes the student's entry from users.yaml; student re-registers.
"""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

# ---------------------------------------------------------------------------
# Allowlist helpers
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email: str) -> bool:
    """Basic email format check."""
    return bool(_EMAIL_RE.match(email))


def auth_enabled(auth_cfg: dict) -> bool:
    """Return True when the educator has configured at least one domain or email."""
    return bool(auth_cfg.get("allowed_domains")) or bool(auth_cfg.get("allowed_emails"))


def is_email_allowed(email: str, auth_cfg: dict) -> bool:
    """Return True if email matches a configured domain or is in the individual list.

    IID-AUTH-BASIC: domain list and per-email list are both checked.
    """
    email = email.strip().lower()
    domain = email.split("@", 1)[-1] if "@" in email else ""
    allowed_domains = [d.strip().lower() for d in auth_cfg.get("allowed_domains", [])]
    allowed_emails = [e.strip().lower() for e in auth_cfg.get("allowed_emails", [])]
    return domain in allowed_domains or email in allowed_emails


# ---------------------------------------------------------------------------
# User-store helpers  (users.yaml, gitignored)
# ---------------------------------------------------------------------------

_USERS_FILE = Path(__file__).parent.parent / "users.yaml"


def _users_path() -> Path:
    return _USERS_FILE


def load_users() -> dict:
    """Load users.yaml; return empty dict if file does not exist yet."""
    path = _users_path()
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    # data structure: { email: { password_hash, created_at } }
    return data.get("users", {})


def _save_users(users: dict) -> None:
    """Persist the users dict back to users.yaml."""
    path = _users_path()
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump({"users": users}, fh, default_flow_style=False, allow_unicode=True)


def find_user(email: str, users: dict) -> Optional[dict]:
    """Return user entry or None."""
    return users.get(email.strip().lower())


# ---------------------------------------------------------------------------
# Password helpers  (bcrypt directly — avoids passlib/bcrypt version mismatch)
# ---------------------------------------------------------------------------

def _hash_password(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _check_password(password: str, hashed: str) -> bool:
    import bcrypt
    return bcrypt.checkpw(password.encode(), hashed.encode())


def register_user(email: str, password: str) -> None:
    """Hash password and add user to users.yaml. IID-AUTH-BASIC."""
    email = email.strip().lower()
    users = load_users()
    users[email] = {
        "password_hash": _hash_password(password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_users(users)


def verify_password(email: str, password: str, users: dict) -> bool:
    """Return True if password matches the stored bcrypt hash."""
    user = find_user(email, users)
    if user is None:
        return False
    return _check_password(password, user["password_hash"])
