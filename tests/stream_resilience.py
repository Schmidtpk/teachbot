"""
IID-STREAM-RESILIENCE, IID-TEST-LLM-EVAL
Offline tests for the streaming watchdog in `app.py::_stream_assistant`.

No Chainlit server, no network: `stream_response` and `cl.Message` are replaced with
stubs so the retry / history-rewind / cleanup behaviour can be asserted directly.

Run:  .venv\\Scripts\\python tests/stream_resilience.py
"""

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import app with the smallest config so startup stays fast and offline-safe.
os.environ.setdefault("TEACHBOT_CONFIG", "config_timeseries.yaml")
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-not-used")

import app  # noqa: E402


# ── stubs ────────────────────────────────────────────────────────────────────────

class FakeMessage:
    """Stands in for cl.Message — records what the student would have seen."""

    def __init__(self, content: str = "") -> None:
        self.content = content
        self.id = "fake-msg-id"
        self.updates = 0

    async def send(self) -> None:
        pass

    async def stream_token(self, token: str) -> None:
        self.content += token

    async def update(self) -> None:
        self.updates += 1


class StreamSpy:
    """Builds fake `stream_response` generators following a scripted plan.

    Each plan entry is either "stall" (never yields) or a string to emit token-wise.
    Records how many streams were opened and how many were properly closed.
    """

    def __init__(self, plan: list[str]) -> None:
        self.plan = plan
        self.opened = 0
        self.closed = 0

    def __call__(self, client, cfg, messages) -> AsyncIterator[str]:
        behaviour = self.plan[min(self.opened, len(self.plan) - 1)]
        self.opened += 1
        spy = self

        async def gen() -> AsyncIterator[str]:
            try:
                if behaviour == "stall":
                    await asyncio.sleep(3600)  # never produces a first token
                    return
                for ch in behaviour:
                    yield ch
            finally:
                spy.closed += 1

        return gen()


# ── harness ──────────────────────────────────────────────────────────────────────

RESULTS: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> None:
    RESULTS.append((ok, label))
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")


async def run_case(plan: list[str], history: list[dict]) -> tuple:
    spy = StreamSpy(plan)
    app.stream_response = spy
    app.cl.Message = FakeMessage
    app.FIRST_TOKEN_TIMEOUT_S = 0.2  # keep the suite fast
    result = await app._stream_assistant(history, {"model": "test/model"})
    return result, spy


async def main() -> None:
    print(f"FIRST_TOKEN_TIMEOUT_S={app.FIRST_TOKEN_TIMEOUT_S}  "
          f"STREAM_RETRIES={app.STREAM_RETRIES}\n")

    # 1 — happy path: one attempt, answer appended to history
    print("case: first attempt succeeds")
    history = [{"role": "system", "content": "sys"}, {"role": "user", "content": "q"}]
    (msg, text, model, ok), spy = await run_case(["hello"], history)
    check(ok is True, "ok=True")
    check(text == "hello", f"text streamed verbatim (got {text!r})")
    check(spy.opened == 1, f"exactly 1 request made (got {spy.opened})")
    check(history[-1] == {"role": "assistant", "content": "hello"},
          "assistant turn appended to history")
    check(len(history) == 3, f"history grew by exactly 1 (got {len(history)})")

    # 2 — stall then success: the retry is what the student actually sees
    print("\ncase: first attempt stalls, retry succeeds")
    history = [{"role": "system", "content": "sys"}, {"role": "user", "content": "q"}]
    (msg, text, model, ok), spy = await run_case(["stall", "recovered"], history)
    check(ok is True, "ok=True — student never sees an error")
    check(text == "recovered", f"retry's answer is returned (got {text!r})")
    check(msg.content == "recovered",
          f"no stall residue in the bubble (got {msg.content!r})")
    check(spy.opened == 2, f"2 requests made (got {spy.opened})")
    check(spy.closed == 2, f"both streams closed, no leak (got {spy.closed})")
    check(history[-1] == {"role": "assistant", "content": "recovered"},
          "only the successful answer is in history")
    check(len(history) == 3, f"history grew by exactly 1 (got {len(history)})")

    # 3 — every attempt stalls: history rewound, prompt dropped
    print("\ncase: every attempt stalls")
    history = [{"role": "system", "content": "sys"}, {"role": "user", "content": "q"}]
    (msg, text, model, ok), spy = await run_case(["stall"], history)
    check(ok is False, "ok=False")
    check(text == app.STREAM_FAILED_MESSAGE, "failure message returned to caller")
    check(msg.content == app.STREAM_FAILED_MESSAGE, "failure message shown to student")
    check(spy.opened == 1 + app.STREAM_RETRIES,
          f"tried {1 + app.STREAM_RETRIES}x (got {spy.opened})")
    check(spy.closed == spy.opened,
          f"every stalled stream closed (opened {spy.opened}, closed {spy.closed})")
    check(history == [{"role": "system", "content": "sys"}],
          f"unanswered prompt dropped, history rewound (got {history})")
    check(not any("taking too long" in h["content"] or
                  app.STREAM_FAILED_MESSAGE in h["content"] for h in history),
          "failure text never enters the LLM history")

    # 4 — empty completion is a success, not a stall
    print("\ncase: model returns an empty completion")
    history = [{"role": "system", "content": "sys"}, {"role": "user", "content": "q"}]
    (msg, text, model, ok), spy = await run_case([""], history)
    check(ok is True, "ok=True — empty answer is not treated as a stall")
    check(spy.opened == 1, f"not retried (got {spy.opened} requests)")

    # 5 — the goal-kickoff shape rewinds identically
    print("\ncase: learning-goals kickoff stalls")
    history = [{"role": "system", "content": "sys"},
               {"role": "assistant", "content": "earlier answer"},
               {"role": "user", "content": app.GOAL_KICKOFF}]
    (msg, text, model, ok), spy = await run_case(["stall"], history)
    check(ok is False, "ok=False")
    check(history == [{"role": "system", "content": "sys"},
                      {"role": "assistant", "content": "earlier answer"}],
          f"kickoff dropped, earlier turns untouched (got {len(history)} entries)")

    failed = [lbl for ok_, lbl in RESULTS if not ok_]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if failed:
        print("FAILED:")
        for lbl in failed:
            print(f"  - {lbl}")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    asyncio.run(main())
