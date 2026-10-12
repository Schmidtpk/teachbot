"""IID-HEALTH-MONITOR: daily check that every deployed instance can still answer students.

Calls `<url>/health` (src/health.py) on each instance and explains every failure in plain
words: the service is down, runs old code, or one of its self-checks failed (OpenRouter key,
account balance, a model, the log Sheet). Exit code 1 if anything failed.

Run daily by `.github/workflows/health.yml` (one job per instance, so GitHub's failure mail
names the broken instance). In GitHub Actions each failure also becomes an error annotation
and a table in the run summary. Stdlib only — no pip install, no secrets.

Usage:
    python scripts/health_check.py                      # all instances in deploys.DEPLOYS
    python scripts/health_check.py --service dcm        # one instance
    python scripts/health_check.py --service x --url http://localhost:8000   # local app
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

from deploys import DEPLOYS, railway_service

sys.stdout.reconfigure(encoding="utf-8")  # Windows console

TIMEOUT_S = 120     # the first call pings every model (each up to 30s, concurrently)
RETRY_AFTER_S = 90  # > the server's 60s cache for a failed result, so the retry re-checks


def fetch(url: str) -> tuple[int | None, str]:
    """GET `url`; (status, body), status None when the server could not be reached."""
    req = urllib.request.Request(url, headers={"User-Agent": "lectos-health-check/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001 — timeouts, DNS, refused connections
        return None, f"{type(exc).__name__}: {exc}"


def diagnose(name: str, base_url: str) -> list[tuple[str, str]]:
    """Problems found on one instance as (title, explanation); [] = healthy."""
    service = railway_service(name)
    logs = f"`railway logs --service {service}`"
    status, body = fetch(f"{base_url.rstrip('/')}/health")
    if status is None:
        return [("unreachable", f"no answer from {base_url} ({body}). The service is down or "
                                f"Railway has an outage — check {logs} and status.railway.com.")]
    try:
        result = json.loads(body)
    except ValueError:
        result = None
    if not isinstance(result, dict) or "checks" not in result:
        if status == 200:  # Chainlit's catch-all answered: the route does not exist yet
            return [("no /health endpoint", f"{base_url} is up but runs code older than this "
                     f"monitor — redeploy {service} (see CLAUDE.md, Deployment).")]
        return [(f"HTTP {status}", f"{base_url}/health answered HTTP {status} without a health "
                 f"report: the app is crashing or did not start (a failed deploy?). Check "
                 f"{logs} and `railway logs --build --service {service}`.")]
    return [(check, info["detail"]) for check, info in result["checks"].items() if not info["ok"]]


def report(name: str, problems: list[tuple[str, str]]) -> None:
    """Print, and in GitHub Actions add error annotations + a run-summary table."""
    if not problems:
        print(f"[ok]   {name}")
    for title, detail in problems:
        print(f"[FAIL] {name} — {title}: {detail}")
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title={railway_service(name)}: {title}::{detail}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"### {railway_service(name)}: {'FAILED' if problems else 'OK'}\n\n")
            if problems:
                fh.write("| Check | Problem |\n|---|---|\n")
                for title, detail in problems:
                    fh.write(f"| {title} | {detail.replace('|', '/')} |\n")
                fh.write("\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--service", choices=sorted(DEPLOYS), action="append",
                    help="instance to check (repeatable; default: all)")
    ap.add_argument("--url", help="override the URL (single --service only), e.g. a local app")
    a = ap.parse_args()
    names = a.service or list(DEPLOYS)
    if a.url and len(names) != 1:
        ap.error("--url needs exactly one --service")
    failed = False
    for name in names:
        url = a.url or DEPLOYS[name]
        problems = diagnose(name, url)
        # one retry: a redeploy or a provider blip should not send a mail (old code stays old)
        if problems and problems[0][0] != "no /health endpoint":
            print(f"[retry] {name}: {problems[0][0]} — checking again in {RETRY_AFTER_S}s")
            time.sleep(RETRY_AFTER_S)
            problems = diagnose(name, url)
        report(name, problems)
        failed = failed or bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
