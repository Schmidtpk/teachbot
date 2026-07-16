"""
SID-LLM-PROVIDER, SID-API-CONFIG, IID-COST-CACHE
Thin async wrapper around OpenRouter's OpenAI-compatible API.
Model, base URL, and API key come from config + .env — never hardcoded.
"""

import json
import os
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI


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

    The caller's message dicts are never mutated — history keeps plain-string content.
    """
    if not messages:
        return messages

    def _mark(msg: dict[str, Any]) -> dict[str, Any]:
        content = msg.get("content")
        if not isinstance(content, str):
            return msg  # already block-form (or unexpected) — leave untouched
        return {
            **msg,
            "content": [{
                "type": "text",
                "text": content,
                "cache_control": {"type": "ephemeral"},
            }],
        }

    out = list(messages)
    if out[0].get("role") == "system":
        out[0] = _mark(out[0])
    if len(out) > 1:
        out[-1] = _mark(out[-1])
    return out


async def stream_response(
    client: AsyncOpenAI,
    cfg: dict[str, Any],
    messages: list[dict[str, str]],
) -> AsyncIterator[str]:
    """
    SID-LLM-PROVIDER: Stream chat completion tokens from OpenRouter.
    Yields text chunks as they arrive.
    """
    llm_cfg = cfg.get("llm", {})
    stream = await client.chat.completions.create(
        model=llm_cfg.get("model", "google/gemini-3-flash-preview"),
        messages=_with_cache_control(messages),  # type: ignore[arg-type]  # IID-COST-CACHE
        temperature=llm_cfg.get("temperature", 0.3),
        max_tokens=llm_cfg.get("max_tokens", 2048),
        stream=True,
    )
    async for chunk in stream:
        token = chunk.choices[0].delta.content or ""
        if token:
            yield token


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
    empty output, invalid JSON) returns {} so a flaky model degrades gracefully to
    the caller's fallback path rather than crashing the turn.
    """
    llm_cfg = cfg.get("llm", {})
    try:
        resp = await client.chat.completions.create(
            model=llm_cfg.get("model", "google/gemini-3-flash-preview"),
            messages=_with_cache_control(messages),  # type: ignore[arg-type]  # IID-COST-CACHE
            temperature=llm_cfg.get("temperature", 0.3),
            max_tokens=llm_cfg.get("max_tokens", 2048),
            response_format={"type": "json_object"},
        )
    except Exception:
        return {}
    content = (resp.choices[0].message.content or "").strip()
    if not content:
        return {}
    try:
        parsed: Any = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        parsed = _salvage_json(content)
    return parsed if isinstance(parsed, dict) else {}
