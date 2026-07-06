"""
IID-LEARN-GOALS
Learning-goals practice mode helpers: sample one uncompleted goal and assemble the
per-goal system prompt that injects ONLY that goal into the LLM context.

A goal is a dict loaded from a course's `_learning_goals.yaml` (see src/course_loader.py):
  { "id": str, "title": str (optional), "goal": str }
"""

import random
from typing import Optional

from src.course_loader import CourseConfig, build_system_prompt

# IID-LEARN-GOALS: internal instruction that triggers the bot to pose the next question.
# Appended to history (not logged as a student turn) so the assistant's reply is a question.
# Shared by app.py (live) and tests/learn_goals.py (IID-TEST-LLM-EVAL) so they stay in sync.
GOAL_KICKOFF = (
    "Pose a single concrete test question for the current learning goal so the student can "
    "demonstrate it. Ask the question directly; do not restate the goal verbatim."
)


def sample_goal(goals: list[dict], completed: set[str]) -> Optional[dict]:
    """IID-LEARN-GOALS: Uniformly pick one goal whose id is not in `completed`.

    Returns None when every goal has been completed. Pure function (no I/O) so it is
    unit-testable without network access.
    """
    remaining = [g for g in goals if g["id"] not in completed]
    if not remaining:
        return None
    return random.choice(remaining)


def build_goal_system_prompt(course: CourseConfig, goal: dict) -> str:
    """IID-LEARN-GOALS, IID-CONTENT-INJECT: Course system prompt + the single current goal.

    Wraps `build_system_prompt` (instructions + injected lecture content) and appends only
    the sampled learning goal, so the model sees exactly one goal at a time.
    """
    base = build_system_prompt(course)
    title = goal.get("title", "")
    header = f"{title}\n{goal['goal']}" if title else goal["goal"]
    return (
        f"{base}\n"
        f"--- CURRENT LEARNING GOAL ---\n{header}\n--- END LEARNING GOAL ---\n"
    )
