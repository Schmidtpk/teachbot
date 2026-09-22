"""
IID-LLM-THINKING, IID-STUDENT-MODEL-CHOICE
Check whether a model accepts OpenRouter's 'reasoning' parameter - and whether it actually
*honours* it - before putting it in a config's `llm.reasoning` or `student_model_choices`.

Two checks, because they answer different questions:

  1. Declared support - does every provider serving this model list 'reasoning' in its
     `supported_parameters`? OpenRouter routes each request to one of them, so a single
     provider without it makes the setting unreliable, not merely rare.
  2. Observed behaviour (`--live`) - send the same prompt with 'reasoning' unset and with
     `{"enabled": false}` and count the reasoning deltas. Declared support does not
     guarantee the model stops thinking when told to.

Usage:
    python scripts/check_reasoning_support.py deepseek/deepseek-v4-flash-0731
    python scripts/check_reasoning_support.py <model> --live
    python scripts/check_reasoning_support.py --config config_timeseries.yaml
"""

import argparse
import asyncio
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml
from dotenv import load_dotenv

load_dotenv()

PROBE = "In one sentence, what is a stationary time series?"


def _api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        sys.exit("[Lectos] OPENROUTER_API_KEY is not set (see .env.example).")
    return key


def declared_support(model: str) -> tuple[int, int, list[str]]:
    """Return (with_reasoning, total, providers_without) across the model's endpoints."""
    req = urllib.request.Request(
        f"https://openrouter.ai/api/v1/models/{model}/endpoints",
        headers={"Authorization": f"Bearer {_api_key()}"},
    )
    with urllib.request.urlopen(req) as resp:
        endpoints = json.load(resp)["data"]["endpoints"]
    without = [
        e.get("provider_name", "?")
        for e in endpoints
        if "reasoning" not in (e.get("supported_parameters") or [])
    ]
    return len(endpoints) - len(without), len(endpoints), without


async def observed_behaviour(model: str) -> None:
    """Send the probe twice - reasoning unset vs disabled - and report the difference."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=_api_key(), base_url="https://openrouter.ai/api/v1")

    async def once(extra_body) -> tuple[int, float | None, float]:
        t0 = time.monotonic()
        reasoning_deltas, first_content = 0, None
        stream = await client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": PROBE}],
            temperature=0.3, max_tokens=512, stream=True, extra_body=extra_body,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta is None:
                continue
            reasoning = getattr(delta, "reasoning", None) or (
                getattr(delta, "model_extra", None) or {}
            ).get("reasoning")
            if reasoning:
                reasoning_deltas += 1
            if delta.content and first_content is None:
                first_content = time.monotonic() - t0
        return reasoning_deltas, first_content, time.monotonic() - t0

    print("\n  live probe:")
    base_deltas, base_first, base_total = await once(None)
    off_deltas, off_first, off_total = await once({"reasoning": {"enabled": False}})
    fmt = lambda v: f"{v:.1f}s" if v is not None else "never"  # noqa: E731
    print(f"    reasoning unset      : {base_deltas:4} reasoning deltas, "
          f"first content {fmt(base_first)}, total {base_total:.1f}s")
    print(f"    reasoning=false      : {off_deltas:4} reasoning deltas, "
          f"first content {fmt(off_first)}, total {off_total:.1f}s")

    if base_deltas == 0:
        print("    -> not a reasoning model (or this provider never streams it): "
              "'reasoning' changes nothing here.")
    elif off_deltas == 0:
        print("    -> HONOURED: setting reasoning=false stopped the chain-of-thought.")
    else:
        print("    -> NOT HONOURED: the model kept reasoning despite reasoning=false. "
              "Do not rely on this setting for this model.")


def models_from_config(path: str) -> list[str]:
    """Every model id a config can actually use: llm.model plus any student choices."""
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    models = []
    if (m := (cfg.get("llm") or {}).get("model")):
        models.append(m)
    for choice in cfg.get("student_model_choices") or []:
        if isinstance(choice, dict) and choice.get("id") not in models:
            models.append(choice["id"])
    return models


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("model", nargs="?", help="OpenRouter model id")
    ap.add_argument("--config", help="check every model used by this config file instead")
    ap.add_argument("--live", action="store_true",
                    help="also send two real requests and compare (costs a few tokens)")
    args = ap.parse_args()

    if args.config:
        models = models_from_config(args.config)
        if not models:
            sys.exit(f"No models found in {args.config}.")
    elif args.model:
        models = [args.model]
    else:
        ap.error("give a model id or --config")

    problems = 0
    for model in models:
        print(f"\n=== {model}")
        try:
            ok, total, without = declared_support(model)
        except Exception as exc:  # noqa: BLE001 - report and continue to the next model
            print(f"  could not read endpoints: {type(exc).__name__}: {exc}")
            problems += 1
            continue
        print(f"  declares 'reasoning': {ok}/{total} providers")
        if without:
            problems += 1
            print(f"  ! providers WITHOUT it: {', '.join(sorted(set(without)))}")
            print("    OpenRouter picks a provider per request, so the setting is not "
                  "reliable for this model.")
        if args.live:
            await observed_behaviour(model)

    print("\nDone." if not problems else f"\nDone - {problems} model(s) need a closer look.")


if __name__ == "__main__":
    asyncio.run(main())
