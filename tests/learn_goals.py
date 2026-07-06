"""
IID-TEST-LLM-EVAL, IID-LEARN-GOALS
Multi-turn test harness for the learning-goals practice mode.

For each goal in a cases file (default: tests/cases/learn_part1_goals.yaml) it checks:
  (a) the INITIAL question the tutor poses for the goal   -> judged against `question_rubric`;
  (b) the tutor's FEEDBACK to a simulated student         -> judged against each turn's `feedback_rubric`.

It exercises the REAL production path: the per-course system prompt (build_system_prompt) plus the
single injected goal (build_goal_system_prompt) plus the shared GOAL_KICKOFF, all from src/. Student
answers are produced live by a "student simulator" LLM persona reacting to the tutor's actual question,
so feedback is graded against an authentic exchange rather than a canned one.

Cases may omit the `goal:` text — then it is pulled from the course's `_learning_goals.yaml` by id,
so the tested prompt is exactly the deployed one (an unknown id is a loud error).

CLI:
    python tests/learn_goals.py
    python tests/learn_goals.py --goal why_probabilistic
    python tests/learn_goals.py --cases tests/cases/learn_part1_goals.yaml
    python tests/learn_goals.py --no-judge        # print transcripts only, no grading
    python tests/learn_goals.py --model z-ai/glm-5.2 --json reports/glm.json   # model override + dump
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))  # for `judge`

from src.course_loader import discover_courses
from src.goals import GOAL_KICKOFF, build_goal_system_prompt
from src.llm_client import build_client, stream_response

DEFAULT_CASES = ROOT / "tests" / "cases" / "learn_part1_goals.yaml"


def _load_cfg() -> dict:
    with (ROOT / "config.yaml").open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _course_by_id(cfg: dict, course_id: str):
    root = Path(cfg.get("content_dir", "content"))
    if not root.is_absolute():
        root = ROOT / root
    courses = {c.course_id: c for c in discover_courses(root, cfg)}
    if course_id not in courses:
        sys.exit(f"[learn_goals] course '{course_id}' not found. Known: {sorted(courses)}")
    return courses[course_id]


async def _retry(make_coro, what: str, attempts: int = 4):
    """Retry an async LLM call on transient errors (streaming drops, empty output)."""
    delay = 2.0
    for i in range(attempts):
        try:
            return await make_coro()
        except Exception as exc:  # noqa: BLE001 — transient network/model hiccups
            if i == attempts - 1:
                raise
            print(f"    [retry] {what}: {type(exc).__name__}: {exc}; retrying in {delay:.0f}s ...")
            await asyncio.sleep(delay)
            delay *= 2


async def _complete(client, cfg: dict, messages: list[dict]) -> str:
    """Collect a full (non-streamed-to-user) completion from the shared streaming client."""
    async def _once() -> str:
        out = ""
        async for token in stream_response(client, cfg, messages):
            out += token
        if not out.strip():
            raise RuntimeError("empty completion")
        return out
    return await _retry(_once, "completion")


async def _judge(question: str, response: str, rubric: str) -> dict:
    """LLM-as-judge with retry; degrades to an ERROR verdict instead of crashing the suite.

    The default judge is the config model (deepseek), a reasoning model that intermittently
    returns empty visible content. We retry, and if it still fails we return verdict ERROR so
    the run completes and reports the other checks. Set JUDGE_MODEL to a stronger/steadier
    grader for reliable verdicts.
    """
    from judge import judge_response  # noqa: PLC0415

    async def _once() -> dict:
        v = await judge_response(question=question, response=response, rubric=rubric)
        if not v.get("explanation"):
            raise RuntimeError("empty judge output")
        return v
    try:
        return await _retry(_once, "judge", attempts=6)
    except Exception as exc:  # noqa: BLE001
        return {"verdict": "ERROR", "explanation": f"judge unavailable after retries ({exc}); "
                f"set JUDGE_MODEL to a steadier grader", "score": 0}


async def _simulate_student(client, cfg: dict, tutor_question: str, instruction: str) -> str:
    """IID-TEST-LLM-EVAL: a student-simulator persona answers the tutor's real question."""
    sys_prompt = (
        "You are role-playing a university student answering a tutor's question in a practice chat. "
        "Stay in character, answer ONLY the tutor's question, and follow these instructions exactly:\n"
        f"{instruction}\n"
        "Do not break character or add meta-commentary."
    )
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": f"Tutor's question:\n{tutor_question}"},
    ]
    return (await _complete(client, cfg, messages)).strip()


async def run_goal(client, cfg: dict, course, goal: dict, do_judge: bool) -> dict:
    """Run one goal: pose the initial question, then each student turn + feedback.

    Returns a record {goal, title, question, checks, turns} — `checks` feeds the pass/fail
    summary, the rest is the transcript for --json / report rendering.
    """
    system_prompt = build_goal_system_prompt(course, goal)

    # (a) initial question -------------------------------------------------
    q_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": GOAL_KICKOFF},
    ]
    tutor_question = (await _complete(client, cfg, q_messages)).strip()

    print(f"\n{'=' * 70}\nGOAL: {goal['id']} — {goal.get('title', '')}")
    print(f"\n[Q] tutor's opening question:\n{tutor_question}")

    record: dict = {"goal": goal["id"], "title": goal.get("title", ""),
                    "question": tutor_question, "checks": [], "turns": []}
    if do_judge:
        v = await _judge(
            question=f"The tutor must pose an opening test question for this learning goal:\n{goal['goal']}",
            response=tutor_question,
            rubric=goal["question_rubric"],
        )
        print(f"    QUESTION VERDICT: {v['verdict']} — {v['explanation']}")
        record["checks"].append({"goal": goal["id"], "check": "question",
                                 "verdict": v["verdict"], "explanation": v["explanation"]})

    # (b) feedback to each simulated student -------------------------------
    for turn in goal.get("student_turns", []):
        persona = turn["persona"]
        student_answer = await _simulate_student(client, cfg, tutor_question, turn["instruction"])
        fb_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": GOAL_KICKOFF},
            {"role": "assistant", "content": tutor_question},
            {"role": "user", "content": student_answer},
        ]
        feedback = (await _complete(client, cfg, fb_messages)).strip()

        print(f"\n  --- persona: {persona} ---")
        print(f"  [student] {student_answer}")
        print(f"  [feedback] {feedback}")
        turn_rec = {"persona": persona, "student": student_answer, "feedback": feedback}
        if do_judge:
            v = await _judge(
                question=f"Tutor asked:\n{tutor_question}\n\nStudent ({persona}) answered:\n{student_answer}",
                response=feedback,
                rubric=turn["feedback_rubric"],
            )
            print(f"  FEEDBACK VERDICT: {v['verdict']} — {v['explanation']}")
            record["checks"].append({"goal": goal["id"], "check": f"feedback:{persona}",
                                     "verdict": v["verdict"], "explanation": v["explanation"]})
            turn_rec["verdict"] = v["verdict"]
            turn_rec["explanation"] = v["explanation"]
        record["turns"].append(turn_rec)

    return record


async def _main_async(args: argparse.Namespace) -> None:
    load_dotenv(ROOT / ".env")
    cfg = _load_cfg()

    cases_path = Path(args.cases) if args.cases else DEFAULT_CASES
    with cases_path.open(encoding="utf-8") as fh:
        spec = yaml.safe_load(fh)

    course = _course_by_id(cfg, spec["course"])
    cfg["llm"] = dict(course.llm)  # use the course's resolved LLM settings (real path)
    if args.model:
        cfg["llm"]["model"] = args.model  # IID-TEST-MODEL-COMPARE: per-run model override
    client = build_client(cfg)

    goals = spec["goals"]
    if args.goal:
        goals = [g for g in goals if g["id"] == args.goal]
        if not goals:
            sys.exit(f"[learn_goals] goal '{args.goal}' not in {cases_path}")

    # IID-LEARN-GOALS: cases without a `goal:` text are bound to the PRODUCTION goal
    # from the course's _learning_goals.yaml, so we test exactly what students see.
    production = {g["id"]: g for g in (course.learning_goals or [])}
    for g in goals:
        if "goal" not in g:
            if g["id"] not in production:
                sys.exit(f"[learn_goals] goal '{g['id']}' has no `goal:` text and is not in "
                         f"the course's _learning_goals.yaml (known: {sorted(production)})")
            g["goal"] = production[g["id"]]["goal"]
            g.setdefault("title", production[g["id"]].get("title", ""))

    all_checks: list[dict] = []
    records: list[dict] = []
    for goal in goals:
        record = await run_goal(client, cfg, course, goal, do_judge=not args.no_judge)
        records.append(record)
        all_checks.extend(record["checks"])

    if args.json:
        json_path = Path(args.json)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps({"model": cfg["llm"]["model"], "course": course.course_id,
                                         "goals": records}, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        print(f"\n(wrote JSON results to {json_path})")

    if not args.no_judge and all_checks:
        passed = sum(c["verdict"] == "PASS" for c in all_checks)
        failed = sum(c["verdict"] == "FAIL" for c in all_checks)
        errored = sum(c["verdict"] == "ERROR" for c in all_checks)
        print(f"\n{'=' * 70}\nSUMMARY: {passed} PASS / {failed} FAIL / {errored} ERROR "
              f"(of {len(all_checks)} checks)")
        marks = {"PASS": "✓", "FAIL": "✗", "ERROR": "?"}
        for c in all_checks:
            print(f"  {marks.get(c['verdict'], '?')} [{c['goal']}] {c['check']}"
                  + (f"  ({c['verdict']})" if c["verdict"] != "PASS" else ""))
        if errored:
            print("\n  NOTE: ERROR = the judge model failed to grade (infra/flakiness), not a tutor "
                  "problem.\n        Re-run, or use JUDGE_MODEL=<steadier model> for reliable verdicts.")
        # Only a real FAIL (tutor quality) fails the suite; judge-infra ERRORs do not.
        if failed:
            sys.exit(1)


class _Tee:
    """Write everything sent to stdout to a file as well, so the full transcript is saved."""

    def __init__(self, stream, fh):
        self._stream = stream
        self._fh = fh

    def write(self, data):
        self._stream.write(data)
        self._fh.write(data)
        return len(data)

    def flush(self):
        self._stream.flush()
        self._fh.flush()


def main() -> None:
    # Windows consoles default to cp1252; LLM output often contains exotic Unicode
    # (e.g. narrow no-break space). Force UTF-8 so printing transcripts never crashes.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    p = argparse.ArgumentParser(description="Lectos learning-goals mode test harness (IID-LEARN-GOALS)")
    p.add_argument("--cases", help=f"Cases YAML (default: {DEFAULT_CASES})")
    p.add_argument("--goal", help="Run only this goal id")
    p.add_argument("--no-judge", action="store_true", help="Print transcripts only, no LLM-as-judge grading")
    p.add_argument("--model", help="Override the course's LLM model (IID-TEST-MODEL-COMPARE)")
    p.add_argument("--json", help="Write structured results (transcripts + verdicts) to this JSON file")
    p.add_argument("--out", help="Also write the full transcript to this file (UTF-8)")
    args = p.parse_args()

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fh = out_path.open("w", encoding="utf-8")
        sys.stdout = _Tee(sys.stdout, fh)
        print(f"(writing transcript to {out_path})")

    asyncio.run(_main_async(args))


if __name__ == "__main__":
    main()
