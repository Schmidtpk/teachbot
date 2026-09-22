"""
IID-LLM-THINKING, IID-STUDENT-MODEL-CHOICE, IID-TEST-LLM-EVAL
Offline tests for the reasoning toggle and the student model chooser.

No network: only the config->request translation and the selection logic are exercised.
Whether a given model actually *honours* the parameter is a live question, answered by
`scripts/check_reasoning_support.py --live`.

Run:  .venv\\Scripts\\python tests/model_choices.py
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("TEACHBOT_CONFIG", "config_timeseries.yaml")
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-not-used")

import yaml  # noqa: E402

import app  # noqa: E402
from src.course_loader import parse_model_choices  # noqa: E402
from src.llm_client import _reasoning_kwargs  # noqa: E402

RESULTS: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> None:
    RESULTS.append((ok, label))
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")


class FakeSession:
    """Stands in for cl.user_session."""

    def __init__(self, **kw) -> None:
        self._d = dict(kw)

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value) -> None:
        self._d[key] = value


def exits(raw, where="test") -> bool:
    """True when parse_model_choices rejects `raw` with a loud SystemExit."""
    try:
        parse_model_choices(raw, where)
    except SystemExit:
        return True
    return False


def main() -> None:
    # 1 — config value -> OpenRouter request body
    print("case: llm.reasoning translation")
    check(_reasoning_kwargs({}) == {},
          "absent -> nothing sent (provider default preserved)")
    check(_reasoning_kwargs({"reasoning": False})
          == {"extra_body": {"reasoning": {"enabled": False}}},
          "false -> {'enabled': False}")
    check(_reasoning_kwargs({"reasoning": True})
          == {"extra_body": {"reasoning": {"enabled": True}}},
          "true -> {'enabled': True}")
    check(_reasoning_kwargs({"reasoning": {"effort": "low"}})
          == {"extra_body": {"reasoning": {"effort": "low"}}},
          "mapping -> passed through verbatim")
    try:
        _reasoning_kwargs({"reasoning": "yes"})
        check(False, "a string is rejected")
    except TypeError:
        check(True, "a string is rejected with TypeError")

    # 2 — choice-list validation
    print("\ncase: student_model_choices validation")
    parsed = parse_model_choices(
        [{"id": "m/a", "label": "Fast", "reasoning": False},
         {"id": "m/a", "label": "Thorough", "reasoning": True}], "test")
    check(len(parsed) == 2, "same model id twice is allowed")
    check(parsed[0]["reasoning"] is False and parsed[1]["reasoning"] is True,
          "each choice keeps its own reasoning setting")
    check(parse_model_choices([{"id": "m/a"}], "test")[0]["label"] == "m/a",
          "label defaults to the id")
    check(parse_model_choices(None, "test") == [], "absent -> no choices, no error")
    check(exits([{"label": "no id"}]), "entry without an id is rejected")
    check(exits("not-a-list"), "non-list is rejected")
    check(exits([{"id": "m/a", "label": "X"}, {"id": "m/b", "label": "X"}]),
          "duplicate labels are rejected (labels are the chooser keys)")
    check(exits([{"id": "m/a", "reasoning": "sometimes"}]),
          "non-bool/non-mapping reasoning is rejected")

    # 3 — applying a choice
    print("\ncase: on_settings_update applies model AND reasoning")
    choices = parse_model_choices(
        [{"id": "m/a", "label": "Fast", "reasoning": False},
         {"id": "m/a", "label": "Thorough", "reasoning": True},
         {"id": "m/b", "label": "Other"}], "test")
    cmap = {c["label"]: c for c in choices}
    session = FakeSession(model_choice_map=cmap,
                          course_llm={"model": "m/a", "reasoning": False})
    app.cl.user_session = session

    asyncio.run(app.on_settings_update({"model": "Thorough"}))
    check(session.get("course_llm") == {"model": "m/a", "reasoning": True},
          f"switching to 'Thorough' turns reasoning on (got {session.get('course_llm')})")

    asyncio.run(app.on_settings_update({"model": "Fast"}))
    check(session.get("course_llm") == {"model": "m/a", "reasoning": False},
          f"switching back turns it off again (got {session.get('course_llm')})")

    asyncio.run(app.on_settings_update({"model": "Other"}))
    check(session.get("course_llm") == {"model": "m/b"},
          f"a choice without `reasoning` clears it (got {session.get('course_llm')})")

    asyncio.run(app.on_settings_update({"model": "Nonexistent"}))
    check(session.get("course_llm") == {"model": "m/b"},
          "an unknown label is ignored, not applied")

    # 4 — the deployed config is internally consistent
    print("\ncase: config_timeseries.yaml")
    cfg = yaml.safe_load((ROOT / "config_timeseries.yaml").read_text(encoding="utf-8"))
    deployed = parse_model_choices(cfg.get("student_model_choices"), "config_timeseries")
    check(len(deployed) == 2, f"two choices offered (got {len(deployed)})")
    check({c["reasoning"] for c in deployed} == {True, False},
          "one with thinking, one without")
    check(cfg["llm"].get("reasoning") is False,
          f"default is the fast, no-thinking variant (got {cfg['llm'].get('reasoning')!r})")
    default_pair = (cfg["llm"]["model"], cfg["llm"].get("reasoning"))
    check(any((c["id"], c.get("reasoning")) == default_pair for c in deployed),
          "the configured default matches one of the offered choices, so the chooser "
          "preselects the right label")

    # 5 — every deploy config still loads
    print("\ncase: all deploy configs import")
    for name in ("config.yaml", "config_public.yaml", "config_dcm.yaml",
                 "config_timeseries.yaml"):
        env = {**os.environ, "TEACHBOT_CONFIG": name}
        proc = subprocess.run(
            [sys.executable, "-c", "import app"], cwd=ROOT, env=env,
            capture_output=True, text=True,
        )
        check(proc.returncode == 0, f"{name} imports cleanly"
              + ("" if proc.returncode == 0 else f" — {proc.stderr.strip()[-200:]}"))

    failed = [lbl for ok_, lbl in RESULTS if not ok_]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if failed:
        print("FAILED:")
        for lbl in failed:
            print(f"  - {lbl}")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
