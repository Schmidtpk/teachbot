"""
IID-TEST-LLM-EVAL
Core test runner: loads test cases from YAML, calls the LLM pipeline
(reusing src/content_loader and src/llm_client), and collects responses.

Reuses the same system prompt construction as app.py. Model, temperature,
and other LLM settings come from config.yaml and can be overridden per run.

CLI:
    python tests/runner.py --cases tests/cases/qna.yaml
    python tests/runner.py --case course_scope --judge
    python tests/runner.py --cases tests/cases/qna.yaml --dry-run
"""

import argparse
import asyncio
import copy
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Ensure project root is on sys.path for src.* imports
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.content_loader import load_content
from src.llm_client import build_client, stream_response


def _load_cfg(llm_overrides: dict | None = None) -> dict:
    """Load config.yaml from project root, apply optional LLM overrides."""
    cfg_path = ROOT / "config.yaml"
    with cfg_path.open(encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    if llm_overrides:
        cfg = copy.deepcopy(cfg)
        cfg.setdefault("llm", {}).update(llm_overrides)
    return cfg


def _build_system_prompt(cfg: dict, course_content: str) -> str:
    """Replicate the system prompt from app.py — must stay in sync."""
    # IID-QNA-CORE: same prompt as app.py
    course_name = cfg.get("course_name", "this course")
    system_prompt_override = cfg.get("_system_prompt_override")
    if system_prompt_override:
        return system_prompt_override.replace("{course_content}", course_content)
    return f"""\
You are a helpful teaching assistant for the course "{course_name}".

Your role is to answer student questions accurately based solely on the lecture content provided below.
- Answer in clear, concise Markdown. Use math notation ($...$ or $$...$$) where appropriate.
- Cite or paraphrase the relevant lecture material in your answer.
- If a question is not covered by the lecture content, say so honestly and do not invent information.
- Politely decline requests unrelated to the course.

--- LECTURE CONTENT START ---
{course_content}
--- LECTURE CONTENT END ---
"""


def load_cases(cases_path: str) -> list[dict]:
    """Load test cases from a YAML file."""
    with open(cases_path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


async def run_case(case: dict, cfg: dict, course_content: str) -> dict:
    """Run a single test case through the LLM pipeline. Returns result dict."""
    client = build_client(cfg)
    system_prompt = _build_system_prompt(cfg, course_content)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": case["question"]},
    ]

    full_response = ""
    async for token in stream_response(client, cfg, messages):
        full_response += token

    return {
        "case_id": case["id"],
        "question": case["question"],
        "response": full_response,
        "rubric": case.get("rubric", ""),
        "tags": case.get("tags", []),
        "model": cfg.get("llm", {}).get("model", "unknown"),
        "temperature": cfg.get("llm", {}).get("temperature", 0.3),
    }


async def run_cases(
    cases: list[dict],
    cfg: dict | None = None,
    llm_overrides: dict | None = None,
) -> list[dict]:
    """
    Run all test cases and return list of result dicts.
    Accepts a pre-built cfg (for compare.py) or loads fresh from config.yaml.
    """
    if cfg is None:
        effective_cfg = _load_cfg(llm_overrides)
    elif llm_overrides:
        effective_cfg = copy.deepcopy(cfg)
        effective_cfg.setdefault("llm", {}).update(llm_overrides)
    else:
        effective_cfg = cfg

    course_content = load_content(effective_cfg.get("content_dir", "content"))
    results = []
    for case in cases:
        print(f"  Running [{case['id']}] ...", end=" ", flush=True)
        result = await run_case(case, effective_cfg, course_content)
        print("done")
        results.append(result)
    return results


async def _main_async(args: argparse.Namespace) -> None:
    if args.dry_run:
        cfg = _load_cfg()
        try:
            load_content(cfg.get("content_dir", "content"))
        except SystemExit as e:
            print(f"[dry-run] FAIL: {e}")
            sys.exit(1)
        cases = load_cases(args.cases) if args.cases else []
        print(f"[dry-run] OK — config loaded, content loaded, {len(cases)} cases parsed.")
        return

    if args.cases:
        cases = load_cases(args.cases)
    elif args.case:
        found = None
        for default_path in ["tests/cases/qna.yaml", "tests/cases/behavior.yaml"]:
            p = ROOT / default_path
            if p.exists():
                for c in load_cases(str(p)):
                    if c["id"] == args.case:
                        found = c
                        break
            if found:
                break
        if not found:
            print(f"Case '{args.case}' not found in default case files.")
            sys.exit(1)
        cases = [found]
    else:
        print("Provide --cases <file.yaml> or --case <id>")
        sys.exit(1)

    results = await run_cases(cases)

    for r in results:
        print(f"\n{'=' * 60}")
        print(f"CASE:  {r['case_id']}")
        print(f"MODEL: {r['model']} | TEMP: {r['temperature']}")
        print(f"Q: {r['question']}")
        print(f"\nA:\n{r['response']}")

        if args.judge:
            if not r["rubric"]:
                print("\n[judge] No rubric defined for this case — skipping.")
                continue
            # Lazy import to allow dry-run without openai installed
            TESTS = Path(__file__).parent
            sys.path.insert(0, str(TESTS))
            from judge import judge_response  # noqa: PLC0415
            verdict = await judge_response(r["question"], r["response"], r["rubric"])
            print(f"\nVERDICT: {verdict['verdict']}")
            print(f"REASON:  {verdict['explanation']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="teachbot LLM test runner")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--cases", help="Path to YAML file with test cases")
    group.add_argument("--case", help="Single case ID to run (searches default case files)")
    parser.add_argument("--judge", action="store_true", help="Grade each response with LLM-as-judge")
    parser.add_argument("--dry-run", action="store_true", help="Validate config + content only, no LLM calls")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    asyncio.run(_main_async(args))


if __name__ == "__main__":
    main()
