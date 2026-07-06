import asyncio, sys, copy
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
load_dotenv(ROOT / ".env")

sys.path.insert(0, str(ROOT / "tests"))
from runner import _load_cfg, load_cases, run_cases
from judge import judge_response

MODELS = [
    ("gemini-flash",    "google/gemini-3-flash-preview"),
    ("deepseek-v4-pro", "deepseek/deepseek-v4-pro"),
    ("claude-sonnet",   "anthropic/claude-sonnet-4-6"),
    ("gemini-pro",      "google/gemini-3.1-pro-preview"),
]

OUT = ROOT / "reports" / "answers_exercise25.md"

async def main():
    cases = load_cases(str(ROOT / "tests/cases/exercise25.yaml"))
    lines = []
    for label, model in MODELS:
        cfg = _load_cfg({"model": model, "temperature": 0.3})
        results = await run_cases(cases, cfg=cfg)
        for r in results:
            verdict = await judge_response(r["question"], r["response"], r["rubric"])
            v = verdict["verdict"]
            lines.append(f"## {label} — {v}\n")
            lines.append(r["response"])
            lines.append("\n")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved -> {OUT}")

asyncio.run(main())
