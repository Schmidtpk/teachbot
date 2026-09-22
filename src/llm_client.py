"""
SID-LLM-PROVIDER, SID-API-CONFIG, IID-COST-CACHE
Thin async wrapper around OpenRouter's OpenAI-compatible API.
Model, base URL, and API key come from config + .env — never hardcoded.
"""

import asyncio
import json
import os
import sys
import time
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

# IID-LEARN-DIAGNOSE: the diagnose call is non-streamed, so nothing is visible to the
# student while it's in flight. Chainlit's Socket.IO layer uses engine.io's default
# ping_timeout (20s) — a call left to hang indefinitely risks the session's transport
# being dropped and reconnected (see agent/session_churn_fix_handoff.md). Fail well
# before that window so the caller's existing empty-dict fallback engages instead.
DIAGNOSE_TIMEOUT_S = 15


def build_client(cfg: dict[str, Any]) -> AsyncOpenAI:
    """SID-LLM-PROVIDER: Create an AsyncOpenAI client pointed at OpenRouter."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "[Lectos] OPENROUTER_API_KEY is not set. "
            "Copy .env.example to .env and add your key."
        )
    llm_cfg = cfg.get("llm", {})
    return AsyncOpenAI(
        api_key=api_key,
        base_url=llm_cfg.get("base_url", "https://openrouter.ai/api/v1"),
    )


def _with_cache_control(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """IID-COST-CACHE: mark the stable prompt prefix as cacheable.

    Converts the system message (instructions + injected lecture content — by far the
    largest part of every request) and the latest message (so the growing conversation
    history is cached incrementally turn-over-turn) to content-block form with an
    Anthropic `cache_control` breakpoint. OpenRouter forwards `cache_control` to
    providers with explicit prompt caching (Anthropic: reads bill at ~0.1x) and drops
    it for providers that cache implicitly or not at all, so this is safe for every
    model in the student chooser (IID-STUDENT-MODEL-CHOICE).

    System messages that already arrive as a content-block list (learning-goals mode
    splits them into a stable lecture-content block + a per-goal block, see
    `src/goals.py::build_goal_system_blocks`) get a breakpoint per text block, so the
    lecture-content prefix is reused across goals and across concurrent students.
    At most 3 blocks are marked per message — Anthropic allows 4 breakpoints per
    request and the latest message uses one.

    The caller's message dicts are never mutated — history keeps plain-string content.
    """
    if not messages:
        return messages

    def _mark(msg: dict[str, Any]) -> dict[str, Any]:
        content = msg.get("content")
        if isinstance(content, str):
            return {
                **msg,
                "content": [{
                    "type": "text",
                    "text": content,
                    "cache_control": {"type": "ephemeral"},
                }],
            }
        if isinstance(content, list):
            marked, budget = [], 3
            for block in content:
                if (budget > 0 and isinstance(block, dict)
                        and block.get("type") == "text" and "cache_control" not in block):
                    block = {**block, "cache_control": {"type": "ephemeral"}}
                    budget -= 1
                marked.append(block)
            return {**msg, "content": marked}
        return msg  # unexpected shape — leave untouched

    out = list(messages)
    if out[0].get("role") == "system":
        out[0] = _mark(out[0])
    if len(out) > 1:
        out[-1] = _mark(out[-1])
    return out


# IID-STREAM-RESILIENCE: the two kinds of delta `stream_events` yields.
REASONING = "reasoning"
CONTENT = "content"


def _reasoning_kwargs(llm_cfg: dict[str, Any]) -> dict[str, Any]:
    """IID-LLM-THINKING: translate the config's `reasoning` setting into OpenRouter's API.

    `reasoning` is an OpenRouter extension, so it travels in `extra_body` rather than as a
    typed parameter of the OpenAI SDK. Accepted values:

        (absent)  → send nothing; the provider's own default applies (current behaviour)
        false     → {"enabled": false}  — no chain-of-thought
        true      → {"enabled": true}
        mapping   → passed through verbatim, e.g. {effort: low} or {max_tokens: 512}

    Whether a model honours this is model- *and provider-specific*: verify before relying on
    it (`python scripts/check_reasoning_support.py <model>`). Verified 2026-09-22 for
    `deepseek/deepseek-v4-flash-0731`: reasoning deltas 211→0 and time-to-first-content
    11.3s→1.2s on the timeseries prompt.
    """
    reasoning = llm_cfg.get("reasoning")
    if reasoning is None:
        return {}
    if isinstance(reasoning, bool):
        return {"extra_body": {"reasoning": {"enabled": reasoning}}}
    if isinstance(reasoning, dict):
        return {"extra_body": {"reasoning": reasoning}}
    raise TypeError(
        f"[Lectos] llm.reasoning must be true, false, or a mapping — got "
        f"{type(reasoning).__name__}: {reasoning!r}"
    )


async def stream_events(
    client: AsyncOpenAI,
    cfg: dict[str, Any],
    messages: list[dict[str, str]],
) -> AsyncIterator[tuple[str, str]]:
    """
    SID-LLM-PROVIDER, IID-STREAM-RESILIENCE: stream deltas from OpenRouter, tagged by kind.

    Yields `(REASONING, text)` and `(CONTENT, text)` as they arrive. Reasoning models
    (e.g. `deepseek/deepseek-v4-flash-0731`) emit hundreds of `reasoning` deltas before
    their first `content` delta — measured 3-10s, with a tail past 70s, on the ~10k-token
    timeseries prompt. Callers need to see those to tell "the model is thinking" from "the
    model is hung"; dropping them silently is what made the 15s watchdog kill healthy
    requests (see IID-STREAM-RESILIENCE).

    OpenRouter exposes reasoning as a non-standard `reasoning` field on the delta, so it
    arrives either as an attribute or in the pydantic model's extra fields depending on
    provider — both are checked.
    """
    llm_cfg = cfg.get("llm", {})
    stream = await client.chat.completions.create(
        model=llm_cfg.get("model", "google/gemini-3-flash-preview"),
        messages=_with_cache_control(messages),  # type: ignore[arg-type]  # IID-COST-CACHE
        temperature=llm_cfg.get("temperature", 0.3),
        max_tokens=llm_cfg.get("max_tokens", 2048),
        stream=True,
        **_reasoning_kwargs(llm_cfg),  # IID-LLM-THINKING
    )
    async for chunk in stream:
        # Usage-only / keepalive chunks carry no choices — indexing [0] would raise.
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta is None:
            continue
        reasoning = getattr(delta, "reasoning", None)
        if not reasoning:
            reasoning = (getattr(delta, "model_extra", None) or {}).get("reasoning")
        if reasoning:
            yield REASONING, reasoning
        if delta.content:
            yield CONTENT, delta.content


async def stream_response(
    client: AsyncOpenAI,
    cfg: dict[str, Any],
    messages: list[dict[str, str]],
) -> AsyncIterator[str]:
    """
    SID-LLM-PROVIDER: Stream chat completion *content* tokens from OpenRouter.

    Content-only view of `stream_events`, kept for callers that have no use for reasoning
    deltas (`tests/runner.py`, `tests/learn_goals.py`).
    """
    async for kind, text in stream_events(client, cfg, messages):
        if kind == CONTENT:
            yield text


def _salvage_json(text: str) -> Any:
    """IID-LEARN-DIAGNOSE: Best-effort recovery when a model wraps JSON in prose/fences.

    Extracts the substring between the first '{' and the last '}' and parses it.
    Returns None when nothing parseable is found.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except (json.JSONDecodeError, ValueError):
        return None


async def complete_json(
    client: AsyncOpenAI,
    cfg: dict[str, Any],
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    """
    IID-LEARN-DIAGNOSE, SID-LLM-PROVIDER: Non-streamed structured completion.

    Requests a JSON object and parses it defensively — any failure (network error,
    empty output, invalid JSON, or exceeding DIAGNOSE_TIMEOUT_S) returns {} so a flaky
    or slow model degrades gracefully to the caller's fallback path rather than
    crashing the turn or hanging the session. Every failure is logged with its type,
    message, and elapsed time — previously this swallowed exceptions silently, which
    is why past session-churn investigations found no error trace at all.
    """
    llm_cfg = cfg.get("llm", {})
    model = llm_cfg.get("model", "google/gemini-3-flash-preview")
    start = time.monotonic()
    try:
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=_with_cache_control(messages),  # type: ignore[arg-type]  # IID-COST-CACHE
                temperature=llm_cfg.get("temperature", 0.3),
                max_tokens=llm_cfg.get("max_tokens", 2048),
                response_format={"type": "json_object"},
                **_reasoning_kwargs(llm_cfg),  # IID-LLM-THINKING
            ),
            timeout=DIAGNOSE_TIMEOUT_S,
        )
    except Exception as exc:
        elapsed = time.monotonic() - start
        print(
            f"[complete_json] model={model} failed after {elapsed:.1f}s: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return {}
    elapsed = time.monotonic() - start
    print(f"[timing] complete_json model={model} took {elapsed:.1f}s", file=sys.stderr)
    content = (resp.choices[0].message.content or "").strip()
    if not content:
        return {}
    try:
        parsed: Any = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        parsed = _salvage_json(content)
    return parsed if isinstance(parsed, dict) else {}
