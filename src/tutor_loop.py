"""
IID-LEARN-DIAGNOSE
Agentic two-step tutoring turn for learning-goals mode (IID-LEARN-GOALS).

Each student answer is handled in two LLM calls instead of one:
  1. diagnose  — a non-streamed, structured-JSON call that ranks the misunderstandings in the
                 student's latest answer and selects the SINGLE most important one, plus whether
                 to `explain` it or `probe` for it (see `Diagnosis`).
  2. act       — the existing streamed reply, seeded with the chosen misconception so it addresses
                 exactly one point and then re-asks the fixed "big question" (built here as an
                 internal instruction via `build_act_instruction`).

Pure orchestration: no Chainlit imports, so it is unit-testable with a stub client.
The diagnose prompt text and lecture content are passed in as strings by the caller (app.py).
"""

from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI

from src.llm_client import complete_json


@dataclass
class Diagnosis:
    """IID-LEARN-DIAGNOSE: structured result of judging one student answer.

    `mastered` is only True when the model explicitly signals the answer meets the goal.
    When the diagnose call fails or returns nothing, `from_raw({})` yields a neutral value
    (not mastered, no misconception) so `build_act_instruction` degrades to generic Socratic
    feedback rather than falsely congratulating the student.
    """
    mastered: bool = False
    requested_solution: bool = False  # student explicitly asked for help/summary/the solution
    candidates: list[str] = field(default_factory=list)
    major_misconception: str = ""
    tactic: str = "probe"          # "explain" | "probe"
    rationale: str = ""            # internal only, never shown to the student

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "Diagnosis":
        """Coerce a parsed JSON object (possibly empty/garbage) into a valid Diagnosis."""
        major = str(raw.get("major_misconception") or "").strip()
        mastered = bool(raw.get("mastered", False))
        tactic = str(raw.get("tactic", "probe")).strip().lower()
        if tactic not in ("explain", "probe"):
            tactic = "probe"
        raw_cands = raw.get("candidates", [])
        candidates = (
            [str(c).strip() for c in raw_cands if str(c).strip()]
            if isinstance(raw_cands, list) else []
        )
        return cls(
            mastered=mastered,
            requested_solution=bool(raw.get("requested_solution", False)),
            candidates=candidates,
            major_misconception=major,
            tactic=tactic,
            rationale=str(raw.get("rationale") or "").strip(),
        )

    def as_dict(self) -> dict[str, Any]:
        """Serialisable form for internal logging (IID-CHAT-LOG / IID-SHEETS-LOG)."""
        return {
            "mastered": self.mastered,
            "requested_solution": self.requested_solution,
            "candidates": self.candidates,
            "major_misconception": self.major_misconception,
            "tactic": self.tactic,
            "rationale": self.rationale,
        }


def _render_dialogue(dialogue: list[dict[str, str]]) -> str:
    """IID-LEARN-DIAGNOSE: render the prior student↔tutor exchange as a plain transcript."""
    labels = {"student": "STUDENT", "tutor": "TUTOR"}
    return "\n\n".join(
        f"{labels.get(turn.get('role', ''), 'STUDENT')}: {turn.get('content', '')}"
        for turn in dialogue
    )


def build_diagnose_messages(
    diagnose_prompt: str, lecture_content: str, goal: dict,
    big_question: str, student_answer: str,
    dialogue: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """IID-LEARN-DIAGNOSE, IID-CONTENT-INJECT: assemble the diagnose call's messages.

    System = diagnostic instructions + lecture content + the current goal + the anchor question.
    User   = the dialogue so far for this goal (roles "student"/"tutor", excluding the latest
    answer) + the student's latest answer to grade, so the judge credits points the student
    already made earlier instead of flagging them as omissions. Kept as a pure function so the
    message shape is unit-testable without any network call.
    """
    title = goal.get("title", "")
    goal_text = goal.get("goal", "")
    goal_block = f"{title}\n{goal_text}" if title else goal_text
    # IID-LEARN-GOALS: goal material (pseudocode/formulas the student was shown) must be
    # visible to the judge too, or correct answers about it would be graded as unfounded.
    material = str(goal.get("material") or "").strip()
    if material:
        goal_block += (
            f"\n\n--- MATERIAL (shown to the student with the question) ---\n"
            f"{material}\n--- END MATERIAL ---"
        )
    system = (
        f"{diagnose_prompt}\n\n"
        f"--- LECTURE CONTENT START ---\n{lecture_content}\n--- LECTURE CONTENT END ---\n\n"
        f"--- CURRENT LEARNING GOAL ---\n{goal_block}\n--- END LEARNING GOAL ---\n\n"
        f"--- BIG QUESTION ---\n{big_question}\n--- END BIG QUESTION ---\n"
    )
    transcript = _render_dialogue(dialogue) if dialogue else ""
    dialogue_block = (
        f"Dialogue so far on this goal (before the latest answer):\n\n"
        f"--- DIALOGUE START ---\n{transcript}\n--- DIALOGUE END ---\n\n"
        if transcript else ""
    )
    user = (
        f"The student was asked the BIG QUESTION above. {dialogue_block}"
        "Here is their latest answer:\n\n"
        f'"""\n{student_answer}\n"""\n\n'
        "Diagnose this answer as instructed and reply with ONLY the JSON object."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


async def diagnose_answer(
    client: AsyncOpenAI, course_llm: dict, diagnose_prompt: str, lecture_content: str,
    goal: dict, big_question: str, student_answer: str,
    dialogue: list[dict[str, str]] | None = None,
) -> Diagnosis:
    """IID-LEARN-DIAGNOSE, IID-COST-CACHE: run the structured diagnose call and return a Diagnosis.

    Uses `diagnose_model` from the merged LLM config when set (a cheap model for this
    non-streamed, never-shown JSON call — the lecture-content-heavy input dominates cost),
    otherwise the course model (SID-LLM-PROVIDER via `complete_json`). The student's model
    choice (IID-STUDENT-MODEL-CHOICE) intentionally does NOT affect the diagnose model.
    Any failure yields `Diagnosis.from_raw({})` → neutral, so the caller falls back to
    generic feedback.
    """
    messages = build_diagnose_messages(
        diagnose_prompt, lecture_content, goal, big_question, student_answer, dialogue
    )
    diag_llm = dict(course_llm)
    if course_llm.get("diagnose_model"):
        diag_llm["model"] = course_llm["diagnose_model"]
    raw = await complete_json(client, {"llm": diag_llm}, messages)
    return Diagnosis.from_raw(raw)


def build_act_instruction(diagnosis: Diagnosis, big_question: str) -> str:
    """IID-LEARN-DIAGNOSE, IID-LEARN-SOCRATIC: internal instruction that seeds the streamed reply.

    Four cases:
      - mastered            → affirm + suggest the ✅ button, no new material.
      - requested solution  → the student explicitly asked for help/a summary/the solution: give the
                              full answer to the big question, then ask them to restate it themselves.
      - has misconception   → address ONLY that point (explain or probe per tactic), then re-ask
                              the fixed big question.
      - neither (diagnosis  → generic Socratic feedback re-asking the big question (degrades to the
        unavailable)         prior single-call behaviour).
    """
    q = big_question.strip()

    if diagnosis.mastered and not diagnosis.major_misconception:
        return (
            "The student's answer is essentially correct and demonstrates the goal. Briefly affirm "
            "what they got right (one or two sentences) and tell them they can click the "
            "'✅ Mark goal complete' button to move on. Do not introduce new material or new questions."
        )

    if diagnosis.requested_solution:
        return (
            "The student has explicitly asked for help, a summary, or the solution — provide it. "
            f'Give a clear, complete answer to the big question: "{q}", grounded in the lecture '
            "content (a short numbered list or a few sentences, whichever fits). Then invite the "
            "student to restate it in their own words, since the goal is demonstrated only once "
            "they can state it themselves."
        )

    if diagnosis.major_misconception:
        if diagnosis.tactic == "explain":
            tactic = (
                "Explain this one point concisely (2-3 sentences), grounded in the lecture content, "
                "without handing over the full answer to the big question."
            )
        else:
            tactic = (
                "Ask ONE focused probing question that leads the student to notice and correct this "
                "point. Do not explain it outright."
            )
        return (
            f'The single most important gap in the student\'s latest answer is: '
            f'"{diagnosis.major_misconception}". {tactic} '
            f'Then ask the student to give an improved answer to the big question: "{q}". '
            f"Keep it short and address only this one point."
        )

    # Diagnosis unavailable (empty/garbage JSON) — behave like the prior single-call tutor.
    return (
        "Give brief Socratic feedback on the student's latest answer: first affirm what is correct, "
        "then point out the most important thing that is missing or wrong without revealing the full "
        f'answer, and ask them to give an improved answer to the big question: "{q}".'
    )
