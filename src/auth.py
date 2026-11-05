"""
IID-AUTH-BASIC
Email-gated authentication helpers for Lectos.

Flow:
  - Educator configures allowed_domains / allowed_emails in config.yaml (auth: section).
  - Students use the Chainlit login form (username = email, password of their choice).
  - First successful login with an allowed email = automatic registration.
  - Subsequent logins verify the stored bcrypt hash.
  - If allowed_domains and allowed_emails are both empty, auth is disabled (public mode).

User accounts are stored in users.yaml (gitignored, created at runtime): on the service's Railway
volume when one is attached, so accounts survive redeploys; otherwise in the repo root.
Password reset: scripts/reset_password.py removes the entry; the student re-registers.
"""

import os
import re
import sys
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


def resolve_auth_cfg(auth_cfg: dict) -> dict:
    """IID-AUTH-BASIC: merge `allowed_emails_env` into `allowed_emails`.

    The repo is public, so a participant list of named students must not live in a config
    file. `allowed_emails_env: SOME_VAR` reads the addresses (separated by commas, semicolons
    or whitespace) from that environment variable — a Railway variable in production.
    A named variable that is unset or empty is a loud startup failure: with both lists empty
    auth would silently switch off and the deploy would be public.
    """
    var = auth_cfg.get("allowed_emails_env")
    if not var:
        return auth_cfg
    raw = os.environ.get(var, "")
    emails = [e for e in re.split(r"[,;\s]+", raw) if e]
    if not emails:
        sys.exit(f"[Lectos] ERROR: auth.allowed_emails_env names '{var}', but that environment "
                 f"variable is unset or empty — refusing to start without a login allowlist.")
    bad = [e for e in emails if not is_valid_email(e)]
    if bad:
        sys.exit(f"[Lectos] ERROR: '{var}' contains invalid email address(es): {', '.join(bad)}")
    return {**auth_cfg, "allowed_emails": [*(auth_cfg.get("allowed_emails") or []), *emails]}


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
    """IID-AUTH-BASIC: Railway sets RAILWAY_VOLUME_MOUNT_PATH when the service has a volume.
    The container's own file system is replaced on every deploy, the volume is not."""
    mount = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
    return Path(mount) / "users.yaml" if mount else _USERS_FILE


def accounts_lost_on_redeploy() -> bool:
    """IID-AUTH-BASIC: running on Railway without a volume, so a deploy wipes all accounts."""
    return bool(os.environ.get("RAILWAY_ENVIRONMENT")) and not os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")


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
    """Persist the users dict back to users.yaml.

    IID-AUTH-BASIC: written to a temp file and swapped in, because the file now outlives the
    container: a deploy stopping the app mid-write must not leave a damaged file behind.
    """
    path = _users_path()
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        yaml.safe_dump({"users": users}, fh, default_flow_style=False, allow_unicode=True)
    os.replace(tmp, path)


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


def delete_user(email: str) -> bool:
    """Password reset: remove the account, the student re-registers. IID-AUTH-BASIC.
    Returns False if there is no such account."""
    users = load_users()
    if users.pop(email.strip().lower(), None) is None:
        return False
    _save_users(users)
    return True


def verify_password(email: str, password: str, users: dict) -> bool:
    """Return True if password matches the stored bcrypt hash."""
    user = find_user(email, users)
    if user is None:
        return False
    return _check_password(password, user["password_hash"])
