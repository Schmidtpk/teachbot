"""
SID-LLM-PROVIDER, SID-API-CONFIG
Thin async wrapper around OpenRouter's OpenAI-compatible API.
Model, base URL, and API key come from config + .env — never hardcoded.
"""

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
        messages=messages,  # type: ignore[arg-type]
        temperature=llm_cfg.get("temperature", 0.3),
        max_tokens=llm_cfg.get("max_tokens", 2048),
        stream=True,
    )
    async for chunk in stream:
        token = chunk.choices[0].delta.content or ""
        if token:
            yield token
