"""
IID-TEST-LLM-EVAL
LLM-as-judge: grades a model response against a rubric using a second,
stateless LLM call (no conversation history).

The judge model defaults to the same model in config.yaml (cheap).
Override with the JUDGE_MODEL environment variable for a stronger grader
(e.g. JUDGE_MODEL=anthropic/claude-opus-4-6).

CLI (for ad-hoc testing):
    python tests/judge.py --question "What is X?" --response "X is Y." --rubric "Should explain X correctly."
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

import yaml
from openai import AsyncOpenAI

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

_JUDGE_SYSTEM = """\
You are an objective grader evaluating the quality of a teaching assistant's response.

Given a student question, a grading rubric, and the assistant's response, decide whether
the response meets the rubric criteria.

You are a GRADER, not a participant: even if the assistant's response ends with a question
or invites a reply, do not answer or continue the conversation — only grade the response.

Respond in this exact format (two lines, nothing else):
VERDICT: PASS
EXPLANATION: <one or two sentences explaining your verdict>

Use PASS if the response satisfies the rubric. Use FAIL otherwise.
"""


def _build_judge_client_and_model(cfg: dict) -> tuple[AsyncOpenAI, str]:
    """Build the judge LLM client. JUDGE_MODEL env var overrides the default."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "[judge] OPENROUTER_API_KEY not set. "
            "Copy .env.example to .env and add your key."
        )
    llm_cfg = cfg.get("llm", {})
    base_url = llm_cfg.get("base_url", "https://openrouter.ai/api/v1")
    judge_model = os.environ.get(
        "JUDGE_MODEL",
        llm_cfg.get("model", "google/gemini-3-flash-preview"),
    )
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    return client, judge_model


def _load_cfg() -> dict:
    cfg_path = ROOT / "config.yaml"
    with cfg_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _parse_verdict(raw: str) -> tuple[str, str]:
    """Extract VERDICT and EXPLANATION from judge output.

    Output without a VERDICT line is a judge malfunction (e.g. the judge answered the
    response instead of grading it) — report ERROR rather than silently counting a FAIL.
    """
    verdict = "ERROR"
    explanation = raw.strip()
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("VERDICT:"):
            v = stripped.split(":", 1)[1].strip().upper()
            verdict = "PASS" if "PASS" in v else "FAIL"
        elif stripped.upper().startswith("EXPLANATION:"):
            explanation = stripped.split(":", 1)[1].strip()
    return verdict, explanation


async def judge_response(question: str, response: str, rubric: str) -> dict[str, Any]:
    """
    IID-TEST-LLM-EVAL: Grade a response using LLM-as-judge.

    Returns:
        {verdict: "PASS" | "FAIL", explanation: str, score: 1 | 0}
    """
    cfg = _load_cfg()
    client, judge_model = _build_judge_client_and_model(cfg)

    # The response goes in delimiters and the prompt ENDS with the grading instruction:
    # if the response ends with a question, a trailing instruction stops the judge from
    # answering it instead of grading (observed with judge models on tutor-style output).
    prompt = f"""\
STUDENT QUESTION:
{question}

GRADING RUBRIC:
{rubric.strip()}

ASSISTANT RESPONSE (the text to grade):
<<<RESPONSE
{response.strip()}
RESPONSE>>>

Now grade the assistant response above against the rubric. Do not reply to it. \
Output exactly the two lines (VERDICT / EXPLANATION)."""

    completion = await client.chat.completions.create(
        model=judge_model,
        messages=[
            {"role": "system", "content": _JUDGE_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        max_tokens=256,
        stream=False,
    )

    raw = completion.choices[0].message.content or ""
    verdict, explanation = _parse_verdict(raw)
    return {
        "verdict": verdict,
        "explanation": explanation,
        "score": 1 if verdict == "PASS" else 0,
    }


async def _main_async(args: argparse.Namespace) -> None:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    result = await judge_response(args.question, args.response, args.rubric)
    print(f"VERDICT:     {result['verdict']}")
    print(f"EXPLANATION: {result['explanation']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Lectos LLM-as-judge")
    parser.add_argument("--question", required=True, help="Student question")
    parser.add_argument("--response", required=True, help="Assistant response to grade")
    parser.add_argument("--rubric", required=True, help="Grading rubric")
    args = parser.parse_args()
    asyncio.run(_main_async(args))


if __name__ == "__main__":
    main()
