"""
IID-LEARN-GOALS
Learning-goals practice mode helpers: sample one uncompleted goal and assemble the
per-goal system prompt that injects ONLY that goal into the LLM context.

A goal is a dict loaded from a course's `_learning_goals.yaml` (see src/course_loader.py):
  { "id": str, "title": str (optional), "goal": str, "material": str (optional) }

`material` holds anything the student must literally see to answer (pseudocode, formulas,
data). The app appends it verbatim to the posed question (see app.py `_pose_goal_question`),
so its display never depends on the LLM copying it out of the goal text.
"""

import random
from typing import Optional

from src.course_loader import CourseConfig, build_system_prompt

# IID-LEARN-GOALS: internal instruction that triggers the bot to pose the next question.
# Appended to history (not logged as a student turn) so the assistant's reply is a question.
# Shared by app.py (live) and tests/learn_goals.py (IID-TEST-LLM-EVAL) so they stay in sync.
GOAL_KICKOFF = (
    "Pose a single concrete test question for the current learning goal so the student can "
    "demonstrate it. Ask the question directly; do not restate the goal verbatim. If the goal "
    "has a MATERIAL block, it is shown to the student automatically right below your question — "
    "refer to it (e.g. 'the pseudocode below') but do not reproduce it yourself."
)


def goal_material(goal: dict) -> str:
    """IID-LEARN-GOALS: verbatim study material (code, formulas, data) of a goal, or ''.

    The app itself appends this below the posed question, so the student always sees it —
    delivery does not rely on the LLM reproducing it from the goal text.
    """
    return str(goal.get("material") or "").strip()


def sample_goal(goals: list[dict], completed: set[str], seed_key: Optional[str] = None) -> Optional[dict]:
    """IID-LEARN-GOALS: Pick one goal whose id is not in `completed`.

    With `seed_key` (stable per student+course, e.g. "email:course") the pick is
    deterministic for a given completed-set: a page reload mid-goal — iPad Safari
    evicts the tab on app switch, restarting the Chainlit session — re-serves the
    SAME goal instead of jumping to a different one. Completing a goal changes the
    completed-set and thus the seed, so the next goal still varies per student.
    Without `seed_key` (auth disabled → no stable identity) falls back to uniform
    random per session. Returns None when every goal has been completed. Pure
    function (no I/O) so it is unit-testable without network access.
    """
    remaining = [g for g in goals if g["id"] not in completed]
    if not remaining:
        return None
    if seed_key is not None:
        rng = random.Random(f"{seed_key}|{','.join(sorted(completed))}")
        return rng.choice(remaining)
    return random.choice(remaining)


def build_goal_system_prompt(course: CourseConfig, goal: dict) -> str:
    """IID-LEARN-GOALS, IID-CONTENT-INJECT: Course system prompt + the single current goal.

    Wraps `build_system_prompt` (instructions + injected lecture content) and appends only
    the sampled learning goal, so the model sees exactly one goal at a time.
    """
    base = build_system_prompt(course)
    title = goal.get("title", "")
    header = f"{title}\n{goal['goal']}" if title else goal["goal"]
    material = goal_material(goal)
    material_part = (
        f"--- MATERIAL (displayed to the student automatically below your opening question; "
        f"refer to it, do not reproduce it) ---\n{material}\n--- END MATERIAL ---\n"
        if material else ""
    )
    return (
        f"{base}\n"
        f"--- CURRENT LEARNING GOAL ---\n{header}\n--- END LEARNING GOAL ---\n"
        f"{material_part}"
    )
