"""
IID-INPUT-WORD-BUDGET, IID-GENERAL-ASSISTANT, IID-AUTH-BASIC, IID-TEST-LLM-EVAL
Offline tests for the replication-seminar deploy (config_seminar.yaml): the per-chat word
budget, the login allowlist read from an environment variable, and running without lecture
content.

Run:  .venv\\Scripts\\python tests/seminar.py
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["TEACHBOT_CONFIG"] = "config_seminar.yaml"
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-not-used")
os.environ.setdefault("SEMINAR_ALLOWED_EMAILS", "a.student@stud.uni-heidelberg.de, Mixed.Case@T-Online.de")

import app  # noqa: E402
from src.auth import auth_enabled, is_email_allowed, resolve_auth_cfg  # noqa: E402

RESULTS: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> None:
    RESULTS.append((ok, label))
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")


def exits(fn) -> bool:
    try:
        fn()
    except SystemExit:
        return True
    return False


class FakeSession:
    """Stands in for cl.user_session."""

    def __init__(self, **kw) -> None:
        self._d = dict(kw)

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value) -> None:
        self._d[key] = value


class FakeMessage:
    sent: list[str] = []

    def __init__(self, content: str = "") -> None:
        self.content = content
        self.id = "fake-msg-id"

    async def send(self) -> None:
        FakeMessage.sent.append(self.content)


def main() -> None:
    print("case: word budget refusal text")
    refuse = app._word_budget_refusal
    check(refuse("one two three", 0, 1000) is None, "fits -> no refusal")
    check(refuse("w " * 1000, 0, 1000) is None, "exactly the budget fits")
    msg = refuse("w " * 120, 900, 1000) or ""
    check("120 words" in msg and "100 of the 1000" in msg, "over -> says words and remainder")
    msg = refuse("hi", 1000, 1000) or ""
    check("used all 1000 words" in msg and "new chat" in msg, "exhausted -> points to a new chat")

    print("\ncase: on_message charges, refuses and refunds")
    FakeMessage.sent.clear()
    app.cl.Message = FakeMessage
    calls: list[list[dict]] = []
    outcome = {"ok": True}

    async def fake_stream(history, course_llm, page_context=None):
        calls.append(list(history))
        if outcome["ok"]:
            history.append({"role": "assistant", "content": "answer"})
            return FakeMessage("answer"), "answer", "m", True
        history.pop()
        return FakeMessage("failed"), "failed", "m", False

    class Log:
        def log(self, *a, **k):
            pass

    session = FakeSession(history=[{"role": "system", "content": "sys"}], logger=Log(),
                          sheets_logger=None, course_llm={"model": "m"}, mode="qa")
    app.cl.user_session = session
    app._stream_assistant = fake_stream
    app._log_stream_failure = lambda *a, **k: None

    async def no_actions(*a, **k):
        pass

    app._send_actions = no_actions
    run = lambda text: asyncio.run(app.on_message(FakeMessage(text)))  # noqa: E731

    run("w " * 600)
    check(session.get("words_used") == 600 and len(calls) == 1, "600 words accepted and charged")
    run("w " * 500)
    check(len(calls) == 1 and "only 400" in FakeMessage.sent[-1], "500 more refused, no LLM call")
    check(session.get("words_used") == 600, "refused message not charged")
    outcome["ok"] = False
    run("w " * 300)
    check(len(calls) == 2 and session.get("words_used") == 600, "failed answer -> words refunded")
    outcome["ok"] = True
    run("w " * 400)
    check(len(calls) == 3 and session.get("words_used") == 1000, "remaining 400 accepted")
    run("one")
    check(len(calls) == 3 and "used all 1000" in FakeMessage.sent[-1], "budget exhausted")

    print("\ncase: login allowlist from an environment variable")
    auth = app.CFG["auth"]
    check(auth_enabled(auth), "seminar deploy has login on")
    check(is_email_allowed("mixed.case@t-online.de", auth), "listed address admitted, any case")
    check(not is_email_allowed("someone.else@stud.uni-heidelberg.de", auth),
          "same domain, not listed -> refused (no domain-wide access)")
    os.environ["LECTOS_TEST_EMPTY"] = " "
    check(exits(lambda: resolve_auth_cfg({"allowed_emails_env": "LECTOS_TEST_EMPTY"})),
          "empty variable -> startup failure, never silently public")
    check(exits(lambda: resolve_auth_cfg({"allowed_emails_env": "LECTOS_TEST_UNSET_VAR"})),
          "unset variable -> startup failure")
    os.environ["LECTOS_TEST_BAD"] = "ok@x.de;not-an-email"
    check(exits(lambda: resolve_auth_cfg({"allowed_emails_env": "LECTOS_TEST_BAD"})),
          "invalid address -> startup failure")
    os.environ["LECTOS_TEST_MERGE"] = "b@x.de\nc@y.de"
    merged = resolve_auth_cfg({"allowed_emails": ["a@x.de"], "allowed_emails_env": "LECTOS_TEST_MERGE"})
    check(merged["allowed_emails"] == ["a@x.de", "b@x.de", "c@y.de"], "merged with the config list")
    check(resolve_auth_cfg({"allowed_domains": ["d.de"]}) == {"allowed_domains": ["d.de"]},
          "no allowed_emails_env -> config unchanged")
    env = {k: v for k, v in os.environ.items() if k != "SEMINAR_ALLOWED_EMAILS"}
    proc = subprocess.run([sys.executable, "-c", "import app"], cwd=ROOT, capture_output=True,
                          text=True, env={**env, "SEMINAR_ALLOWED_EMAILS": ""})
    check(proc.returncode != 0 and "SEMINAR_ALLOWED_EMAILS" in proc.stderr,
          "seminar app refuses to start without its allowlist")

    print("\ncase: general assistant without lecture content")
    check(app._GENERAL_ASSISTANT and not app.COURSES, "general_assistant on, single-course")
    content = app.load_content(app._ROOT_CONTENT, allow_empty=True)
    check(content == "", "content_seminar/ holds no lecture content")
    check(exits(lambda: app.load_content(app._ROOT_CONTENT)), "other deploys still fail on empty content")

    failed = [lbl for ok_, lbl in RESULTS if not ok_]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if failed:
        print("FAILED:")
        for lbl in failed:
            print(f"  - {lbl}")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
