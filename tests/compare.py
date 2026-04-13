"""
IID-TEST-MODEL-COMPARE
Runs all test cases through each model/prompt variant defined in
tests/configs/variants.yaml, judges each response, and writes a
comparison report to reports/compare_<timestamp>.md.

CLI:
    python tests/compare.py
    python tests/compare.py --cases tests/cases/qna.yaml tests/cases/behavior.yaml
    python tests/compare.py --variants tests/configs/variants.yaml
"""

import argparse
import asyncio
import copy
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
TESTS = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TESTS))

from runner import _load_cfg, load_cases, run_cases  # noqa: E402
from judge import judge_response  # noqa: E402

DEFAULT_CASES = [
    str(TESTS / "cases" / "qna.yaml"),
    str(TESTS / "cases" / "behavior.yaml"),
]
DEFAULT_VARIANTS = str(TESTS / "configs" / "variants.yaml")
REPORTS_DIR = ROOT / "reports"


def load_variants(variants_path: str) -> list[dict]:
    with open(variants_path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data.get("variants", [])


def _render_markdown_table(rows: list[dict]) -> str:
    if not rows:
        return "_No results._"
    headers = list(rows[0].keys())

    def cell_width(h: str) -> int:
        return max(len(h), max(len(str(r[h])) for r in rows))

    col_widths = {h: cell_width(h) for h in headers}

    def fmt_row(r: dict) -> str:
        return "| " + " | ".join(str(r[h]).ljust(col_widths[h]) for h in headers) + " |"

    sep = "| " + " | ".join("-" * col_widths[h] for h in headers) + " |"
    lines = [fmt_row({h: h for h in headers}), sep] + [fmt_row(r) for r in rows]
    return "\n".join(lines)


def _truncate(text: str, max_len: int = 120) -> str:
    return text if len(text) <= max_len else text[: max_len - 3] + "..."


async def _run_compare(cases_paths: list[str], variants_path: str) -> None:
    # Load all cases
    all_cases: list[dict] = []
    for path in cases_paths:
        p = Path(path)
        if not p.exists():
            print(f"[warn] Cases file not found: {path} — skipping.")
            continue
        all_cases.extend(load_cases(str(p)))

    if not all_cases:
        print("No test cases found. Exiting.")
        sys.exit(1)

    variants = load_variants(variants_path)
    if not variants:
        print(f"No variants found in {variants_path}. Exiting.")
        sys.exit(1)

    base_cfg = _load_cfg()
    all_rows: list[dict] = []

    for variant in variants:
        vid = variant["id"]
        variant_cfg = copy.deepcopy(base_cfg)

        # Apply LLM overrides
        for key in ("model", "temperature", "max_tokens"):
            if key in variant:
                variant_cfg.setdefault("llm", {})[key] = variant[key]

        # Optional full system prompt override (must contain {course_content} placeholder)
        if variant.get("system_prompt_override"):
            variant_cfg["_system_prompt_override"] = variant["system_prompt_override"]

        model_str = variant_cfg.get("llm", {}).get("model", "?")
        print(f"\n--- Variant: {vid} ({model_str}) ---")

        results = await run_cases(all_cases, cfg=variant_cfg)

        for result in results:
            rubric = result.get("rubric", "").strip()
            if rubric:
                print(f"  Judging [{result['case_id']}] ...", end=" ", flush=True)
                verdict = await judge_response(result["question"], result["response"], rubric)
                print(verdict["verdict"])
            else:
                verdict = {
                    "verdict": "N/A",
                    "explanation": "No rubric provided",
                    "score": 0,
                }

            all_rows.append({
                "Case": result["case_id"],
                "Variant": vid,
                "Model": result["model"],
                "Verdict": verdict["verdict"],
                "Explanation": _truncate(verdict["explanation"]),
            })

    # Summary stats per variant
    summary_lines: list[str] = []
    for variant in variants:
        vid = variant["id"]
        judged = [r for r in all_rows if r["Variant"] == vid and r["Verdict"] != "N/A"]
        if judged:
            passes = sum(1 for r in judged if r["Verdict"] == "PASS")
            summary_lines.append(f"- **{vid}**: {passes}/{len(judged)} PASS")

    ts_iso = datetime.now(timezone.utc).isoformat(timespec="seconds") + " UTC"
    ts_file = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    report = (
        f"# teachbot LLM Comparison Report\n\n"
        f"Generated: {ts_iso}\n\n"
        f"## Summary\n\n"
        + ("\n".join(summary_lines) if summary_lines else "_No judged results._")
        + f"\n\n## Results\n\n"
        + _render_markdown_table(all_rows)
        + "\n"
    )

    REPORTS_DIR.mkdir(exist_ok=True)
    report_path = REPORTS_DIR / f"compare_{ts_file}.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nReport saved → {report_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="teachbot model comparison runner")
    parser.add_argument(
        "--cases",
        nargs="+",
        default=DEFAULT_CASES,
        help="YAML file(s) with test cases",
    )
    parser.add_argument(
        "--variants",
        default=DEFAULT_VARIANTS,
        help="YAML file with model variants",
    )
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    asyncio.run(_run_compare(args.cases, args.variants))


if __name__ == "__main__":
    main()
