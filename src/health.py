"""
IID-HEALTH-MONITOR, SID-LLM-PROVIDER, SID-API-CONFIG
Self-check behind the `/health` route: can this deploy still answer students?

Each Railway service tests itself with its *own* secrets, so the daily monitor
(`scripts/health_check.py`, run by `.github/workflows/health.yml`) needs none:

- `openrouter_key` — the key is valid, not expired, and its spend cap has room left
- `openrouter_credit` — the OpenRouter account balance is above a floor
- `llm` — one tiny completion per model this deploy can use answers without error
- `sheets` — the log Sheet opens with the service-account key (read-only)

The result is cached for CACHE_TTL_S: the route needs no login, and the cache bounds
what anyone hitting it can cost (at most one tiny request per model per TTL).
The JSON never contains amounts or secrets — only whether each check passed and, if
not, what to do about it.
"""

import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from openai import AsyncOpenAI

CACHE_TTL_S = 600
# A failed result is kept only briefly, so the monitor's retry (90s later) re-checks.
FAILED_CACHE_TTL_S = 60
LLM_TIMEOUT_S = 30
HTTP_TIMEOUT_S = 15
# 16, not 1: some providers (OpenAI) reject a lower output limit. Still well under a cent.
LLM_PING_MAX_TOKENS = 16
# Floors, overridable per deploy under `health:` in the config yaml.
DEFAULT_MIN_ACCOUNT_CREDIT_USD = 10.0
DEFAULT_MIN_KEY_REMAINING_USD = 1.0
KEY_EXPIRY_WARN_DAYS = 7

_cache: dict[str, Any] = {"at": 0.0, "result": None}
_lock = asyncio.Lock()


def _check(ok: bool, detail: str) -> dict[str, Any]:
    return {"ok": ok, "detail": detail}


def _openrouter_get(base_url: str, path: str) -> dict[str, Any]:
    """Blocking GET of an OpenRouter account endpoint with this deploy's key."""
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/{path}",
        headers={"Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY', '')}"},
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
        return json.load(resp).get("data") or {}


def check_key(base_url: str, min_remaining: float) -> dict[str, Any]:
    """IID-HEALTH-MONITOR: key valid, not (nearly) expired, spend cap not exhausted."""
    try:
        data = _openrouter_get(base_url, "key")
    except urllib.error.HTTPError as exc:
        return _check(False, f"OpenRouter rejected the key (HTTP {exc.code}) — revoked or "
                             f"mistyped? Check the service's OPENROUTER_API_KEY variable.")
    except Exception as exc:  # noqa: BLE001 — any failure is a failed check
        return _check(False, f"could not reach OpenRouter: {type(exc).__name__}: {exc}")
    expires = data.get("expires_at")
    if expires:
        when = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
        if when < datetime.now(timezone.utc) + timedelta(days=KEY_EXPIRY_WARN_DAYS):
            return _check(False, f"key expires {when:%Y-%m-%d} — create a new one and set "
                                 f"OPENROUTER_API_KEY on the service")
    remaining = data.get("limit_remaining")
    if remaining is not None and remaining < min_remaining:
        reset = data.get("limit_reset")
        hint = f" (resets {reset})" if reset else " — raise the key's limit on openrouter.ai/settings/keys"
        return _check(False, f"key spend cap nearly used up: below ${min_remaining:g} left{hint}")
    return _check(True, "key valid, spend cap has room")


def check_credit(base_url: str, min_credit: float) -> dict[str, Any]:
    """IID-HEALTH-MONITOR: account balance (shared by all keys) above the floor."""
    try:
        data = _openrouter_get(base_url, "credits")
        left = float(data["total_credits"]) - float(data["total_usage"])
    except Exception as exc:  # noqa: BLE001
        return _check(False, f"could not read the account balance: {type(exc).__name__}: {exc}")
    if left < min_credit:
        return _check(False, f"OpenRouter balance below ${min_credit:g} — top up at "
                             f"openrouter.ai/settings/credits")
    return _check(True, f"balance above ${min_credit:g}")


async def check_model(client: AsyncOpenAI, model: str) -> dict[str, Any]:
    """IID-HEALTH-MONITOR: one tiny completion. Success = the request returns at all;
    empty content is fine (a reasoning model may spend the few tokens thinking)."""
    start = time.monotonic()
    try:
        await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Reply with OK."}],
                max_tokens=LLM_PING_MAX_TOKENS,
            ),
            timeout=LLM_TIMEOUT_S,
        )
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).replace("\n", " ")[:300]
        return _check(False, f"{type(exc).__name__}: {msg}")
    return _check(True, f"answered in {time.monotonic() - start:.1f}s")


def check_sheets(sheet_id: str | None) -> dict[str, Any]:
    """IID-HEALTH-MONITOR, IID-SHEETS-LOG: the log Sheet opens with the service account.
    Read-only — writes nothing, so the Sheet's contents are untouched."""
    if not sheet_id:
        return _check(True, "Sheets logging not configured")
    if not os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"):
        return _check(False, "sheets_log_id is set but GOOGLE_SERVICE_ACCOUNT_JSON is missing — "
                             "chat turns are not reaching the Sheet")
    try:
        from src.chat_logger import gspread_client  # noqa: PLC0415 — heavy import, only here
        gspread_client().open_by_key(sheet_id).sheet1.row_values(1)
    except Exception as exc:  # noqa: BLE001
        return _check(False, f"cannot open the log Sheet: {type(exc).__name__}: {str(exc)[:200]} "
                             f"— is it still shared with the service account?")
    return _check(True, "log Sheet reachable")


def models_in_use(cfg: dict[str, Any], course_llms: list[dict[str, Any]],
                  model_choices: list[dict[str, Any]]) -> list[str]:
    """IID-HEALTH-MONITOR, IID-STUDENT-MODEL-CHOICE: every model a student can end up
    talking to — the deploy default, each course's model, the diagnose model and every
    chooser option. Order kept, duplicates dropped."""
    seen: list[str] = []
    for llm in [cfg.get("llm", {}), *course_llms]:
        for key in ("model", "diagnose_model"):
            if llm.get(key) and llm[key] not in seen:
                seen.append(llm[key])
    for choice in model_choices:
        if choice["id"] not in seen:
            seen.append(choice["id"])
    return seen


async def run_checks(client: AsyncOpenAI, cfg: dict[str, Any], models: list[str]) -> dict[str, Any]:
    """IID-HEALTH-MONITOR: run every check concurrently; `ok` only if all pass."""
    base_url = cfg.get("llm", {}).get("base_url", "https://openrouter.ai/api/v1")
    health_cfg = cfg.get("health") or {}
    key, credit, sheets, *llm = await asyncio.gather(
        asyncio.to_thread(check_key, base_url, float(health_cfg.get(
            "min_key_remaining_usd", DEFAULT_MIN_KEY_REMAINING_USD))),
        asyncio.to_thread(check_credit, base_url, float(health_cfg.get(
            "min_account_credit_usd", DEFAULT_MIN_ACCOUNT_CREDIT_USD))),
        asyncio.to_thread(check_sheets, cfg.get("sheets_log_id")),
        *(check_model(client, m) for m in models),
    )
    checks = {"openrouter_key": key, "openrouter_credit": credit, "sheets": sheets}
    checks.update({f"llm:{m}": r for m, r in zip(models, llm)})
    result = {
        "ok": all(c["ok"] for c in checks.values()),
        "course_name": cfg.get("course_name", ""),
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "checks": checks,
    }
    if not result["ok"]:
        failed = {k: v["detail"] for k, v in checks.items() if not v["ok"]}
        print(f"[health] FAILED: {failed}", file=sys.stderr)
    return result


async def cached_checks(client: AsyncOpenAI, cfg: dict[str, Any], models: list[str]) -> dict[str, Any]:
    """IID-HEALTH-MONITOR: `run_checks`, at most once per CACHE_TTL_S; concurrent callers
    wait for the one run in flight instead of starting their own."""
    async with _lock:
        cached = _cache["result"]
        ttl = CACHE_TTL_S if cached and cached["ok"] else FAILED_CACHE_TTL_S
        if cached is None or time.monotonic() - _cache["at"] > ttl:
            _cache["result"] = await run_checks(client, cfg, models)
            _cache["at"] = time.monotonic()
        return _cache["result"]
