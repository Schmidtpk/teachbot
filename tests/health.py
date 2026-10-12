"""
IID-HEALTH-MONITOR
Offline tests for the /health self-check and the daily monitor script.

No network: OpenRouter, the LLM, Google Sheets and the HTTP fetch are all faked.
The live end-to-end run is `python scripts/health_check.py --service <x> --url <local app>`.

Run:  .venv\\Scripts\\python tests/health.py
"""

import asyncio
import os
import sys
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

os.environ.setdefault("TEACHBOT_CONFIG", "config_timeseries.yaml")
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-not-used")

import yaml  # noqa: E402

import app  # noqa: E402
import health_check  # noqa: E402
from deploys import DEPLOYS  # noqa: E402
from src import health  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")  # Windows console

RESULTS: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> None:
    RESULTS.append((ok, label))
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")


class FakeCompletions:
    def __init__(self, fail: set[str]) -> None:
        self.fail, self.calls = fail, []

    async def create(self, model, messages, max_tokens):
        self.calls.append((model, max_tokens))
        if model in self.fail:
            raise RuntimeError(f"No endpoints found for {model}")
        return object()


class FakeClient:
    def __init__(self, fail: set[str] = frozenset()) -> None:
        self.chat = type("Chat", (), {})()
        self.chat.completions = FakeCompletions(set(fail))


def main() -> int:
    print("case: models in use")
    models = health.models_in_use(
        {"llm": {"model": "a", "diagnose_model": "b"}},
        [{"model": "a"}, {"model": "c"}],
        [{"id": "c"}, {"id": "d"}, {"id": "a"}],
    )
    check(models == ["a", "b", "c", "d"], f"default, diagnose, course, chooser — deduplicated: {models}")
    check(app.CFG["llm"]["model"] in app._HEALTH_MODELS, f"timeseries deploy pings {app._HEALTH_MODELS}")

    print("\ncase: OpenRouter key and balance")
    orig_get = health._openrouter_get
    try:
        health._openrouter_get = lambda b, p: {"limit_remaining": 30, "expires_at": None}
        check(health.check_key("u", 1.0)["ok"], "key with room on its cap passes")
        health._openrouter_get = lambda b, p: {"limit_remaining": None}
        check(health.check_key("u", 1.0)["ok"], "key without a cap passes")
        health._openrouter_get = lambda b, p: {"limit_remaining": 0.4, "limit_reset": "daily"}
        r = health.check_key("u", 1.0)
        check(not r["ok"] and "daily" in r["detail"] and "0.4" not in r["detail"],
              f"nearly exhausted cap fails, amount not disclosed: {r['detail']}")
        health._openrouter_get = lambda b, p: {"expires_at": "2026-01-01T00:00:00Z"}
        check(not health.check_key("u", 1.0)["ok"], "expired key fails")

        def reject(b, p):
            raise urllib.error.HTTPError("u", 401, "Unauthorized", None, None)
        health._openrouter_get = reject
        r = health.check_key("u", 1.0)
        check(not r["ok"] and "401" in r["detail"], f"rejected key fails: {r['detail']}")
        health._openrouter_get = lambda b, p: {"total_credits": 100, "total_usage": 95}
        r = health.check_credit("u", 10.0)
        check(not r["ok"] and "top up" in r["detail"] and "5" not in r["detail"],
              f"low balance fails, amount not disclosed: {r['detail']}")
        health._openrouter_get = lambda b, p: {"total_credits": 100, "total_usage": 50}
        check(health.check_credit("u", 10.0)["ok"], "healthy balance passes")
    finally:
        health._openrouter_get = orig_get

    print("\ncase: Sheets")
    check(health.check_sheets(None)["ok"], "no sheets_log_id → nothing to check")
    saved = os.environ.pop("GOOGLE_SERVICE_ACCOUNT_JSON", None)
    try:
        r = health.check_sheets("sheet-id")
        check(not r["ok"] and "GOOGLE_SERVICE_ACCOUNT_JSON" in r["detail"], "missing key JSON fails")
    finally:
        if saved is not None:
            os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"] = saved

    print("\ncase: run_checks + cache")
    health.check_key = lambda b, m: {"ok": True, "detail": "k"}
    health.check_credit = lambda b, m: {"ok": True, "detail": "c"}
    health.check_sheets = lambda s: {"ok": True, "detail": "s"}
    client = FakeClient(fail={"broken/model"})
    res = asyncio.run(health.run_checks(client, {}, ["good/model", "broken/model"]))
    check(not res["ok"] and res["checks"]["llm:good/model"]["ok"]
          and "No endpoints" in res["checks"]["llm:broken/model"]["detail"],
          "one failing model fails the whole report and names the model")
    check(all(mt <= 16 for _, mt in client.chat.completions.calls), "LLM ping is capped at 16 tokens")

    async def cache_run():
        health._cache.update(at=0.0, result=None)
        c = FakeClient()
        a = await health.cached_checks(c, {}, ["m"])
        b = await health.cached_checks(c, {}, ["m"])
        n_ok = len(c.chat.completions.calls)
        health._cache.update(at=0.0, result=None)
        f = FakeClient(fail={"m"})
        await health.cached_checks(f, {}, ["m"])
        health._cache["at"] -= health.FAILED_CACHE_TTL_S + 1
        await health.cached_checks(f, {}, ["m"])
        return a is b, n_ok, len(f.chat.completions.calls)
    same, n_ok, n_fail = asyncio.run(cache_run())
    check(same and n_ok == 1, "a passing result is reused (one LLM call for two requests)")
    check(n_fail == 2, "a failed result expires after FAILED_CACHE_TTL_S, so the retry re-checks")

    print("\ncase: /health route")
    from fastapi.testclient import TestClient
    paths = [getattr(r, "path", "") for r in app.chainlit_app.router.routes]
    check(paths.index("/health") < paths.index("/{full_path:path}"), "/health sits before the catch-all")
    health._cache.update(at=0.0, result=None)
    orig_client = app.LLM_CLIENT
    app.LLM_CLIENT = FakeClient()
    try:
        r = TestClient(app.chainlit_app).get("/health")
        check(r.status_code == 200 and r.json()["ok"], "healthy deploy → 200 with JSON, no login needed")
        health._cache.update(at=0.0, result=None)
        app.LLM_CLIENT = FakeClient(fail=set(app._HEALTH_MODELS))
        r = TestClient(app.chainlit_app).get("/health")
        check(r.status_code == 503 and not r.json()["ok"], "failing check → 503")
    finally:
        app.LLM_CLIENT = orig_client

    print("\ncase: monitor script explains failures")
    orig_fetch = health_check.fetch
    try:
        health_check.fetch = lambda u: (None, "URLError: timed out")
        p = health_check.diagnose("dcm", "https://x")
        check(p[0][0] == "unreachable" and "teachbot-dcm" in p[0][1], f"down: {p[0][1][:70]}…")
        health_check.fetch = lambda u: (200, "<html>chainlit</html>")
        p = health_check.diagnose("dcm", "https://x")
        check(p[0][0] == "no /health endpoint" and "redeploy" in p[0][1], "old code: says redeploy")
        health_check.fetch = lambda u: (502, "Application failed to respond")
        p = health_check.diagnose("public", "https://x")
        check(p[0][0] == "HTTP 502" and "--build" in p[0][1], "crashed app: points at the logs")
        health_check.fetch = lambda u: (503, '{"ok": false, "checks": {"sheets": {"ok": false, '
                                             '"detail": "cannot open"}, "llm:m": {"ok": true, "detail": "1s"}}}')
        check(health_check.diagnose("public", "https://x") == [("sheets", "cannot open")],
              "failed self-check: only the failing check is reported")
        health_check.fetch = lambda u: (200, '{"ok": true, "checks": {"llm:m": {"ok": true, "detail": "1s"}}}')
        check(health_check.diagnose("public", "https://x") == [], "healthy → no problems")
    finally:
        health_check.fetch = orig_fetch

    print("\ncase: workflow matrix")
    wf = yaml.safe_load((ROOT / ".github/workflows/health.yml").read_text(encoding="utf-8"))
    matrix = wf["jobs"]["health"]["strategy"]["matrix"]["service"]
    check(sorted(matrix) == sorted(DEPLOYS), f"health.yml matrix == deploys.DEPLOYS ({matrix})")

    failed = [label for ok, label in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
