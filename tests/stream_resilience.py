"""
IID-STREAM-RESILIENCE, IID-TEST-LLM-EVAL
Offline tests for the streaming watchdog in `app.py::_stream_assistant`.

No Chainlit server, no network: `stream_events`, `cl.Message` and `cl.Step` are replaced
with stubs so retry / history-rewind / cleanup / reasoning-liveness behaviour can be
asserted directly.

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
from src.llm_client import CONTENT, REASONING  # noqa: E402

# Short deadlines keep the suite fast; the ratios match the production constants.
TOKEN_GAP = 0.2       # stands in for FIRST_TOKEN_TIMEOUT_S
CONTENT_CAP = 1.0     # stands in for FIRST_CONTENT_TIMEOUT_S


# ── stubs ────────────────────────────────────────────────────────────────────────

class FakeMessage:
    """Stands in for cl.Message — records what the student would have seen."""

    def __init__(self, content: str = "") -> None:
        self.content = content
        self.id = "fake-msg-id"

    async def send(self) -> None:
        pass

    async def stream_token(self, token: str) -> None:
        self.content += token

    async def update(self) -> None:
        pass


class FakeStep:
    """Stands in for cl.Step — records the 'Thinking…' step and anything shown in it."""

    instances: list["FakeStep"] = []

    def __init__(self, name: str = "", type: str = "") -> None:  # noqa: A002
        self.name = name
        self.output = ""
        self.streamed = ""
        self.sent = False
        FakeStep.instances.append(self)

    async def send(self) -> None:
        self.sent = True

    async def stream_token(self, token: str) -> None:
        self.streamed += token

    async def update(self) -> None:
        pass


class StreamSpy:
    """Builds fake `stream_events` generators from a scripted plan.

    A plan entry is a list of steps, each one of:
        ("R", text)      → yield a reasoning delta
        ("C", text)      → yield a content delta
        ("sleep", secs)  → stay silent for `secs`
    The literal string "stall" is shorthand for "never yield anything".
    Records how many streams were opened and how many were properly closed.
    """

    def __init__(self, plan: list) -> None:
        self.plan = plan
        self.opened = 0
        self.closed = 0

    def __call__(self, client, cfg, messages) -> AsyncIterator[tuple[str, str]]:
        script = self.plan[min(self.opened, len(self.plan) - 1)]
        self.opened += 1
        spy = self

        async def gen() -> AsyncIterator[tuple[str, str]]:
            try:
                if script == "stall":
                    await asyncio.sleep(3600)
                    return
                for kind, payload in script:
                    if kind == "sleep":
                        await asyncio.sleep(payload)
                    elif kind == "R":
                        yield REASONING, payload
                    else:
                        yield CONTENT, payload
            finally:
                spy.closed += 1

        return gen()


# ── harness ──────────────────────────────────────────────────────────────────────

RESULTS: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> None:
    RESULTS.append((ok, label))
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")


async def run_case(plan: list, history: list[dict], show_reasoning: bool = True) -> tuple:
    FakeStep.instances.clear()
    spy = StreamSpy(plan)
    app.stream_events = spy
    app.cl.Message = FakeMessage
    app.cl.Step = FakeStep
    app.FIRST_TOKEN_TIMEOUT_S = TOKEN_GAP
    app.FIRST_CONTENT_TIMEOUT_S = CONTENT_CAP
    result = await app._stream_assistant(history, {"model": "test/model"}, show_reasoning)
    return result, spy


def fresh() -> list[dict]:
    return [{"role": "system", "content": "sys"}, {"role": "user", "content": "q"}]


def say(text: str) -> list:
    return [("C", ch) for ch in text]


async def main() -> None:
    print(f"token gap={TOKEN_GAP}s  content cap={CONTENT_CAP}s  "
          f"STREAM_RETRIES={app.STREAM_RETRIES}\n")

    # 1 — happy path
    print("case: first attempt succeeds")
    history = fresh()
    (msg, text, model, ok), spy = await run_case([say("hello")], history)
    check(ok is True, "ok=True")
    check(text == "hello", f"text streamed verbatim (got {text!r})")
    check(spy.opened == 1, f"exactly 1 request made (got {spy.opened})")
    check(history[-1] == {"role": "assistant", "content": "hello"},
          "assistant turn appended to history")
    check(not FakeStep.instances, "no Thinking step for a non-reasoning model")

    # 2 — stall then success
    print("\ncase: first attempt stalls, retry succeeds")
    history = fresh()
    (msg, text, model, ok), spy = await run_case(["stall", say("recovered")], history)
    check(ok is True, "ok=True — student never sees an error")
    check(msg.content == "recovered",
          f"no stall residue in the bubble (got {msg.content!r})")
    check(spy.opened == 2, f"2 requests made (got {spy.opened})")
    check(spy.closed == 2, f"both streams closed, no leak (got {spy.closed})")
    check(len(history) == 3 and history[-1]["content"] == "recovered",
          "only the successful answer is in history")

    # 3 — every attempt stalls
    print("\ncase: every attempt stalls")
    history = fresh()
    (msg, text, model, ok), spy = await run_case(["stall"], history)
    check(ok is False, "ok=False")
    check(msg.content == app.STREAM_FAILED_MESSAGE, "failure message shown to student")
    check(spy.opened == 1 + app.STREAM_RETRIES,
          f"tried {1 + app.STREAM_RETRIES}x (got {spy.opened})")
    check(spy.closed == spy.opened, "every stalled stream closed")
    check(history == [{"role": "system", "content": "sys"}],
          f"unanswered prompt dropped, history rewound (got {history})")
    check(not any(app.STREAM_FAILED_MESSAGE in h["content"] for h in history),
          "failure text never enters the LLM history")

    # 4 — empty completion is a success
    print("\ncase: model returns an empty completion")
    history = fresh()
    (msg, text, model, ok), spy = await run_case([[]], history)
    check(ok is True, "ok=True — empty answer is not treated as a stall")
    check(spy.opened == 1, f"not retried (got {spy.opened} requests)")

    # 5 — THE STAGE-B FIX: reasoning deltas keep a slow model alive
    print("\ncase: reasoning keeps the stream alive past the token gap")
    history = fresh()
    slow = [("sleep", TOKEN_GAP * 0.7), ("R", "thinking "),
            ("sleep", TOKEN_GAP * 0.7), ("R", "harder "),
            ("sleep", TOKEN_GAP * 0.7)] + say("answer")
    (msg, text, model, ok), spy = await run_case([slow], history)
    check(ok is True, "ok=True — silence covered by reasoning is not a stall")
    check(text == "answer", f"content delivered (got {text!r})")
    check(spy.opened == 1, f"no retry needed (got {spy.opened} requests)")
    check(msg.content == "answer", "reasoning text never leaks into the answer bubble")
    check(len(FakeStep.instances) == 1 and FakeStep.instances[0].name == "Thinking…",
          "a Thinking step was shown")
    check(FakeStep.instances[0].streamed == "thinking harder ",
          f"reasoning streamed into the step (got {FakeStep.instances[0].streamed!r})")

    # 6 — reasoning is hidden in learning-goals mode
    print("\ncase: show_reasoning=False (learning-goals mode)")
    history = fresh()
    (msg, text, model, ok), spy = await run_case([slow], history, show_reasoning=False)
    check(ok is True, "ok=True")
    check(text == "answer", "content still delivered")
    check(len(FakeStep.instances) == 1, "a Thinking step is still shown")
    check(FakeStep.instances[0].streamed == "",
          f"chain-of-thought NOT revealed (got {FakeStep.instances[0].streamed!r})")
    check("Thought for" in FakeStep.instances[0].output,
          f"neutral summary instead (got {FakeStep.instances[0].output!r})")

    # 7 — endless reasoning still gives up at the content ceiling
    print("\ncase: model reasons forever, never produces content")
    history = fresh()
    forever = [("sleep", TOKEN_GAP * 0.5), ("R", "x")] * 200
    (msg, text, model, ok), spy = await run_case([forever], history)
    check(ok is False, "ok=False — content ceiling enforced")
    check(spy.opened == 1 + app.STREAM_RETRIES, f"retried then gave up (got {spy.opened})")
    check(spy.closed == spy.opened, "endless streams closed, not leaked")
    check(history == [{"role": "system", "content": "sys"}], "history rewound")

    # 8 — goal-kickoff shape rewinds identically
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
