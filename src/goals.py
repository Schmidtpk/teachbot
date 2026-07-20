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


def sample_goal(goals: list[dict], completed: set[str]) -> Optional[dict]:
    """IID-LEARN-GOALS: Uniformly pick one goal whose id is not in `completed`.

    Returns None when every goal has been completed. Pure function (no I/O) so it is
    unit-testable without network access.

    Note: a mid-goal page reload (e.g. iPad Safari evicting a backgrounded tab) starts a
    fresh Chainlit session and may re-sample a different goal than the one in progress —
    a deterministic per-student seed was tried (2026-07-08) to pin the same goal across
    such reloads, but was reverted 2026-07-20 because under session-churn conditions it
    instead relocked students onto one goal and silently regenerated/reworded its opening
    question dozens of times per hour while resetting in-session mastery progress on every
    restart — a worse and more confusing failure than the occasional reload it fixed.
    """
    remaining = [g for g in goals if g["id"] not in completed]
    if not remaining:
        return None
    return random.choice(remaining)


def build_goal_system_blocks(course: CourseConfig, goal: dict) -> list[dict]:
    """IID-LEARN-GOALS, IID-CONTENT-INJECT, IID-COST-CACHE: system prompt as two content blocks.

    Block 1 — instructions + injected lecture content (`build_system_prompt`): identical for
    every goal and every student of the course, so the cache breakpoint `_with_cache_control`
    places on it (src/llm_client.py) is shared across goals and across concurrent sessions.
    Block 2 — the single sampled goal: changes per goal, kept out of the stable prefix so a
    goal switch only re-writes this small block instead of the whole system prompt.
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
    goal_part = (
        f"\n--- CURRENT LEARNING GOAL ---\n{header}\n--- END LEARNING GOAL ---\n"
        f"{material_part}"
    )
    return [
        {"type": "text", "text": base},
        {"type": "text", "text": goal_part},
    ]


def build_goal_system_prompt(course: CourseConfig, goal: dict) -> str:
    """IID-LEARN-GOALS: plain-string form of `build_goal_system_blocks` (same bytes, joined).

    Kept for callers that need a single string (tests/learn_goals.py harness).
    """
    return "".join(block["text"] for block in build_goal_system_blocks(course, goal))
