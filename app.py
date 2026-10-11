"""
IID-CHAT-SHELL1, IID-QNA-CORE, IID-UI-RENDER, IID-AUTH-BASIC, IID-STUDENT-FEEDBACK-STORE,
IID-MULTI-COURSE, IID-UI-CONTENT-VIEW, IID-UI-CONTENT-CONTEXT, IID-UI-CONTENT-MARK
Chainlit entry point for Lectos v1.
Run with:  chainlit run app.py
"""

import asyncio
import json
import os
import sys
import time
import uuid
from datetime import date
from pathlib import Path
from typing import Optional

import chainlit as cl
from chainlit.auth import get_current_user  # IID-UI-CONTENT-VIEW: login check for viewer files
from chainlit.input_widget import Select
from chainlit.server import app as chainlit_app  # IID-UI-CONTENT-VIEW: extra FastAPI route
from chainlit.utils import utc_now  # IID-STREAM-RESILIENCE: Step start/end timestamps
import yaml
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.responses import FileResponse

from src.auth import auth_enabled, find_user, is_email_allowed, is_valid_email, load_users, register_user, verify_password
from src.chat_logger import ChatLogger, SheetsLogger
from src.content_loader import load_content
from src.course_loader import ROOT_COURSE_ID, CourseConfig, build_system_prompt, discover_courses, load_course_content, load_course_text, load_root_viewer, parse_model_choices
from src.goals import GOAL_KICKOFF, build_goal_system_blocks, goal_material, sample_goal
from src.llm_client import CONTENT, REASONING, build_client, stream_events
from src.progress_store import ProgressStore
from src.tutor_loop import build_act_instruction, diagnose_answer
from src.viewer_docs import ViewerSet

# SID-API-CONFIG: load secrets from .env (never hardcoded)
load_dotenv()

# Load educator config — IID-EDUCATOR-CONFIG, SID-API-CONFIG
# IID-MULTI-DEPLOY: TEACHBOT_CONFIG selects this deploy's config file (default config.yaml).
# Several Railway services can run this same repo, each with its own config → own content
# folder, auth rules, model, and log sheet (e.g. teachbot-public → config_public.yaml).
_cfg_path = Path(__file__).parent / os.environ.get("TEACHBOT_CONFIG", "config.yaml")
if not _cfg_path.is_file():
    sys.exit(f"TEACHBOT_CONFIG points to a missing config file: {_cfg_path}")
with _cfg_path.open(encoding="utf-8") as fh:
    CFG: dict = yaml.safe_load(fh)

# IID-LLM-PROVIDER: single shared async client (model overrides flow through cfg, not the client)
LLM_CLIENT = build_client(CFG)

# IID-MULTI-COURSE: discover course subfolders at startup; [] = single-course fallback mode
_ROOT_CONTENT = Path(CFG.get("content_dir", "content"))
COURSES: list[CourseConfig] = discover_courses(_ROOT_CONTENT, CFG)

# IID-UI-CONTENT-VIEW: single-course mode reads HTML from the content root; with courses,
# each CourseConfig carries its own `viewer`. None everywhere = feature invisible.
ROOT_VIEWER: ViewerSet | None = None if COURSES else load_root_viewer(_ROOT_CONTENT)


def _viewer_for(course_id: str, user: cl.User | None) -> ViewerSet | None:
    """IID-UI-CONTENT-VIEW, IID-COURSE-ACCESS: the viewer documents of `course_id`, if
    this user may open that course right now — same rules as the profile chooser."""
    if not COURSES:
        return ROOT_VIEWER if course_id == ROOT_COURSE_ID else None
    course = next((c for c in COURSES if c.course_id == course_id), None)
    if course is None or course.viewer is None:
        return None
    email = user.identifier if user else None
    if not course.is_available(date.today()) or not course.is_accessible(email):
        return None
    return course.viewer


@chainlit_app.get("/viewer/{course_id}/{filename}")
async def serve_viewer_file(course_id: str, filename: str, user=Depends(get_current_user)):
    """IID-UI-CONTENT-VIEW: serve a course's HTML to the viewer panel's iframe.

    Not under /public (served to anyone): with login enabled, `get_current_user` reads
    Chainlit's auth cookie and rejects requests without one (401). Only files indexed at
    startup are served, so no path from the URL ever reaches the file system.
    `no-cache` = revalidate via ETag: a 7 MB deck is downloaded once, not on every open.
    """
    viewer = _viewer_for(course_id, user)
    doc = next((d for d in viewer.docs.values() if d.filename == filename), None) if viewer else None
    if doc is None:
        raise HTTPException(status_code=404)
    return FileResponse(doc.path, media_type="text/html",
                        headers={"Cache-Control": "private, no-cache"})


# IID-UI-CONTENT-VIEW: importing chainlit.server already registered its catch-all GET
# route (`/{full_path:path}` → the chat UI). Starlette matches in order, so a route added
# afterwards is never reached — move ours in front.
chainlit_app.router.routes.insert(0, chainlit_app.router.routes.pop())


_AUTH_CFG = CFG.get("auth", {})


# IID-EDUCATOR-CONFIG, IID-MULTI-DEPLOY: Chainlit serves the sidebar/welcome panel from the
# fixed path chainlit.md at the project root — there is no per-deploy option. So chainlit.md is
# GENERATED at startup (gitignored) from <content_dir>/_readme.md, falling back to
# content/_readme.md, with {{course_name}} substituted — every deploy then shows its own course.
# The HTML <meta description> (Chainlit's [UI] description) is set from the same name.
def _write_sidebar_readme() -> None:
    course_name = CFG.get("course_name", "this course")
    template = _ROOT_CONTENT / "_readme.md"
    if not template.is_file():
        template = Path("content") / "_readme.md"
    if not template.is_file():
        sys.exit(f"[Lectos] ERROR: no _readme.md found in '{_ROOT_CONTENT}' or 'content/'.")
    text = load_course_text(template, course_name)
    (Path(__file__).parent / "chainlit.md").write_text(text, encoding="utf-8")
    cl.config.config.ui.description = f"Your AI study companion for {course_name}"


_write_sidebar_readme()

# IID-PUBLIC-RATELIMIT: optional per-session caps, set only in no-login deploy configs
# (e.g. config_public.yaml). Best-effort cost damping, not security — a page reload
# starts a fresh session and resets the counter.
_LIMITS = CFG.get("limits") or {}

# IID-STUDENT-MODEL-CHOICE: validated at import so a malformed list stops the deploy
# rather than silently showing students a chooser with an option missing.
_SINGLE_COURSE_MODEL_CHOICES = parse_model_choices(
    CFG.get("student_model_choices"), f"the deploy config ({_cfg_path.name})"
)

# IID-LEARN-GOALS, IID-LEARN-DIAGNOSE: Chainlit's Socket.IO layer uses engine.io's
# default ping_timeout (20s); a stalled LLM call with no visible activity risks the
# session's transport being dropped and reconnected (see
# agent/session_churn_fix_handoff.md). Bail out well before that window so the
# student gets a clear retry prompt instead of a silent session restart.
# IID-STREAM-RESILIENCE: this is the gap between deltas of *any* kind — a reasoning delta
# counts as liveness, so it now means "the connection is dead", not "the model is slow".
FIRST_TOKEN_TIMEOUT_S = 15

# IID-STREAM-RESILIENCE: absolute ceiling from request start to the first *content* delta.
# A reasoning model can stay silent far longer than FIRST_TOKEN_TIMEOUT_S while still
# streaming reasoning; this bounds that patience. Measured on teachbot-timeseries: content
# normally starts within 3-10s, with a long tail past 70s — 45s keeps the tail without
# making a student stare at a spinner for over a minute.
FIRST_CONTENT_TIMEOUT_S = 45

# IID-STREAM-RESILIENCE: extra attempts after a stalled one, before the student sees an
# error. OpenRouter serves a model from many providers of very different speed (29 for
# deepseek-v4-flash as of 2026-09), so a stall is usually bad routing luck rather than a
# broken model — a second request often lands on a fast provider. Kept at 1: each retry
# costs another FIRST_TOKEN_TIMEOUT_S of silence for the student.
STREAM_RETRIES = 1

# IID-STREAM-RESILIENCE: shown only when every attempt stalled. Deliberately does not say
# "send it again" — the failures measured on teachbot-timeseries were largely deterministic
# per question (a student sent the same question 3x and got this 3x), so re-sending
# unchanged is the one thing least likely to help.
STREAM_FAILED_MESSAGE = (
    "⚠️ The model is not responding right now — I tried twice. "
    "Please wait a moment and rephrase your question, or ask something else."
)


@cl.set_chat_profiles
async def set_chat_profiles(user: cl.User | None) -> list[cl.ChatProfile] | None:
    """IID-MULTI-COURSE: Expose course subfolders as Chainlit chat profiles.

    Returns None when no subfolders exist, suppressing the profile chooser and
    preserving single-course behavior. Courses outside their `first_date`/`last_date`
    window in `_meta.yaml` are filtered out. If COURSES is non-empty but every course
    is currently out of window, returns [] (empty chooser) rather than None — falling
    back to single-course mode would silently load root content/, which is wrong.

    IID-COURSE-ACCESS: courses with an `access` block are additionally filtered by the
    logged-in user's email (None when auth is disabled → restricted courses hidden).
    """
    if not COURSES:
        return None
    today = date.today()
    user_email = user.identifier if user else None
    visible = [c for c in COURSES if c.is_available(today) and c.is_accessible(user_email)]
    profiles: list[cl.ChatProfile] = []
    for i, course in enumerate(visible):
        base_desc = course.description or f"**{course.lecture_name}**"
        line = course.availability_line()
        desc = f"{base_desc}\n\n{line}" if line else base_desc
        profiles.append(cl.ChatProfile(
            name=course.lecture_name,
            markdown_description=desc,
            default=(i == 0),
        ))
    return profiles


# IID-AUTH-BASIC: password-based login/registration.
# Only active when auth.allowed_domains or auth.allowed_emails is non-empty in config.yaml.
# If auth is disabled (both lists empty), Chainlit skips the login screen entirely.
if auth_enabled(_AUTH_CFG):
    @cl.password_auth_callback
    async def auth_callback(username: str, password: str) -> Optional[cl.User]:
        """Validate credentials.  First login with an allowed email = registration."""
        email = username.strip().lower()

        if not is_valid_email(email):
            return None

        if not is_email_allowed(email, _AUTH_CFG):
            return None

        users = load_users()
        user = find_user(email, users)

        if user is None:
            # First login → register with chosen password (no strength requirements)
            register_user(email, password)
            return cl.User(identifier=email)

        if verify_password(email, password, users):
            return cl.User(identifier=email)

        return None  # wrong password


async def _aclose(token_stream) -> None:
    """IID-STREAM-RESILIENCE: release a stalled stream's underlying HTTP connection.

    After `asyncio.wait_for` cancels `__anext__`, the generator is left suspended; without
    an explicit close its connection is only reclaimed whenever the GC gets to it. Closing
    can itself raise (the generator may be in a cancelled/running state), which must never
    take down the turn — hence the broad catch.
    """
    try:
        await token_stream.aclose()
    except Exception as exc:  # noqa: BLE001 — best-effort cleanup, never fatal
        print(f"[_aclose] {type(exc).__name__}: {exc}", file=sys.stderr)


def _with_page_context(history: list[dict], page_context: str | None) -> list[dict]:
    """IID-UI-CONTENT-CONTEXT: request-only copy of `history` with the open page in front
    of the latest student message.

    Never stored: the history keeps a one-line marker instead, so it does not grow by a
    slide per turn, and the long system prompt in front stays identical across turns
    (provider prompt caching, IID-COST-CACHE).
    """
    if not page_context or not history or history[-1].get("role") != "user":
        return history
    last = history[-1]
    return history[:-1] + [
        {**last, "content": f"{page_context}\n\nStudent's message:\n{last['content']}"}
    ]


async def _stream_once(
    history: list[dict], course_llm: dict, response_msg: cl.Message,
    show_reasoning: bool = True, page_context: str | None = None,
) -> tuple[bool, str]:
    """IID-STREAM-RESILIENCE: one streaming attempt into `response_msg`.

    Returns (ok, text). `ok=False` means the attempt stalled; the stream is closed and
    nothing has been written to the message, so the caller can retry on a clean slate.
    An empty completion (the stream ends before any content) is a *successful* empty
    answer, not a stall.

    Two deadlines, because a reasoning model is legitimately silent for a long time:
      * FIRST_TOKEN_TIMEOUT_S — between deltas of *any* kind. Reasoning counts as
        liveness, so "thinking hard" is no longer mistaken for "hung".
      * FIRST_CONTENT_TIMEOUT_S — absolute ceiling from request start to the first
        *content* delta, so an endlessly-ruminating model still gives up eventually.
    Once content starts flowing the answer is visibly streaming and no deadline applies —
    aborting there would throw away a half-written answer that the student can already read.

    Reasoning deltas drive a "Thinking…" step. Their text is only shown when
    `show_reasoning` is True: in learning-goals mode the chain-of-thought contains the
    expected answer, so revealing it would hand the student exactly what the Socratic
    dialogue is meant to draw out of them.
    """
    events = stream_events(
        LLM_CLIENT, {"llm": course_llm}, _with_page_context(history, page_context)  # IID-UI-CONTENT-CONTEXT
    ).__aiter__()
    start = time.monotonic()
    thinking: cl.Step | None = None
    text = ""

    async def close_thinking(reasoned_for: float) -> None:
        if thinking is None:
            return
        if not show_reasoning:
            thinking.output = f"Thought for {reasoned_for:.0f}s."
        thinking.end = utc_now()
        await thinking.update()

    while True:
        if text:  # content is already streaming — let it finish unpoliced
            try:
                kind, chunk = await events.__anext__()
            except StopAsyncIteration:
                break
        else:
            remaining = FIRST_CONTENT_TIMEOUT_S - (time.monotonic() - start)
            if remaining <= 0:
                print(
                    f"[_stream_once] no content after {FIRST_CONTENT_TIMEOUT_S}s "
                    f"of reasoning — giving up on this attempt",
                    file=sys.stderr,
                )
                await close_thinking(time.monotonic() - start)
                await _aclose(events)
                return False, ""
            try:
                kind, chunk = await asyncio.wait_for(
                    events.__anext__(), timeout=min(FIRST_TOKEN_TIMEOUT_S, remaining)
                )
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError:
                await close_thinking(time.monotonic() - start)
                await _aclose(events)
                return False, ""

        if kind == REASONING:
            if thinking is None:
                # Managed by hand rather than `async with`, because the step has to open on
                # the first reasoning delta and close on the first content delta — mid-loop.
                # `start`/`end` are what Chainlit's own __aenter__/__aexit__ set, and give
                # the step its duration display.
                thinking = cl.Step(name="Thinking…", type="tool")
                thinking.start = utc_now()
                await thinking.send()
            if show_reasoning:
                await thinking.stream_token(chunk)
        else:
            if thinking is not None and not text:
                await close_thinking(time.monotonic() - start)
            text += chunk
            await response_msg.stream_token(chunk)

    if thinking is not None and not text:  # reasoned, then returned nothing
        await close_thinking(time.monotonic() - start)
    return True, text


async def _stream_assistant(
    history: list[dict], course_llm: dict, show_reasoning: bool = True,
    page_context: str | None = None,
) -> tuple[cl.Message, str, str, bool]:
    """IID-QNA-CORE, IID-UI-RENDER, IID-STREAM-RESILIENCE: stream one assistant turn.

    Returns (message, text, active_model, ok). Caller is responsible for logging.

    A stalled attempt (no first token within FIRST_TOKEN_TIMEOUT_S) is retried
    automatically — OpenRouter spreads a model across many providers of very different
    speed, so a fresh request usually lands somewhere faster. Only when every attempt
    stalls does the student see an error, and in that case `history` is rewound to its
    pre-call state: the unanswered prompt is dropped so a manual retry sends one clean
    turn instead of a transcript in which the tutor repeatedly apologises to itself.

    `show_reasoning=False` keeps a reasoning model's chain-of-thought hidden behind a
    neutral "Thinking…" step — required in learning-goals mode, where it would spoil the
    answer the Socratic dialogue is supposed to elicit.

    `page_context` (IID-UI-CONTENT-CONTEXT): the page open in the viewer panel, added to
    the request only (see `_with_page_context`).
    """
    active_model = course_llm.get("model", "")  # IID-STUDENT-MODEL-CHOICE
    response_msg = cl.Message(content="")
    await response_msg.send()

    start = time.monotonic()
    for attempt in range(1 + STREAM_RETRIES):
        ok, text = await _stream_once(history, course_llm, response_msg, show_reasoning, page_context)
        if ok:
            await response_msg.update()
            print(
                f"[timing] _stream_assistant model={active_model} "
                f"took {time.monotonic() - start:.1f}s (attempt {attempt + 1})",
                file=sys.stderr,
            )
            history.append({"role": "assistant", "content": text})
            return response_msg, text, active_model, True
        print(
            f"[_stream_assistant] model={active_model} no token after "
            f"{FIRST_TOKEN_TIMEOUT_S}s (attempt {attempt + 1}/{1 + STREAM_RETRIES})",
            file=sys.stderr,
        )

    # IID-STREAM-RESILIENCE: every attempt stalled. Drop the prompt that went unanswered
    # (student question, goal kickoff, or act instruction — always the trailing user entry)
    # so the next turn starts from exactly the history we had before this call.
    if history and history[-1].get("role") == "user":
        history.pop()

    print(
        f"[_stream_assistant] model={active_model} gave up after "
        f"{time.monotonic() - start:.1f}s",
        file=sys.stderr,
    )
    text = STREAM_FAILED_MESSAGE
    response_msg.content = text
    await response_msg.update()
    return response_msg, text, active_model, False


def _log_stream_failure(
    logger: ChatLogger, sheets_logger: "SheetsLogger | None", text: str, model: str,
) -> None:
    """IID-STREAM-RESILIENCE, IID-CHAT-LOG, IID-SHEETS-LOG: record a stall as its own role.

    Logged as `error`, never `assistant` — the educator's logs must not imply the bot said
    something useful, and a distinct role makes the stall rate directly countable in the
    Sheet (which is how the teachbot-timeseries 13.7% figure was measured in the first place).
    """
    logger.log("error", text, model=model)
    if sheets_logger:
        sheets_logger.log("error", text, model=model)


async def _send_actions(message_id: str, full_response: str, mode: str) -> None:
    """IID-STUDENT-FEEDBACK-STORE, IID-LEARN-GOALS: attach per-message action buttons."""
    await cl.Action(
        name="flag",
        label="🚩 Flag this response",
        payload={"flagged_message": full_response},
    ).send(for_id=message_id)
    if mode == "learning_goals":  # IID-LEARN-GOALS: let the student mark the goal complete
        current_goal: dict | None = cl.user_session.get("current_goal")
        # IID-LEARN-GOALS: carry the goal id so stale buttons (from earlier goals) can be
        # detected in on_complete_goal instead of completing the *current* goal.
        await cl.Action(
            name="complete_goal",
            label="✅ Mark goal complete",
            payload={"goal_id": current_goal["id"] if current_goal else None},
        ).send(for_id=message_id)


async def _pose_goal_question(
    history: list[dict], course_llm: dict, logger: ChatLogger,
    sheets_logger: "SheetsLogger | None", mode: str,
) -> None:
    """IID-LEARN-GOALS: append the internal kickoff turn, stream + log the bot's question."""
    history.append({"role": "user", "content": GOAL_KICKOFF})  # internal, not logged
    # IID-LEARN-GOALS: hide reasoning — it would reveal the answer to the question being posed
    response_msg, full_response, active_model, ok = await _stream_assistant(
        history, course_llm, show_reasoning=False)
    if not ok:
        # IID-STREAM-RESILIENCE: no question was posed, so there is no "big question" to
        # diagnose against — recording a stall as the goal's question would poison the
        # whole goal. Clearing it makes the next student message re-pose the question
        # (see the learning-goals branch of `on_message`) instead of diagnosing an answer
        # to a question that was never asked.
        cl.user_session.set("current_big_question", "")
        _log_stream_failure(logger, sheets_logger, full_response, active_model)
        return
    # IID-LEARN-GOALS: goal material (pseudocode/formulas the student must see) is appended
    # verbatim by the app itself — display never depends on the LLM copying it from the goal.
    material = goal_material(cl.user_session.get("current_goal") or {})
    if material:
        full_response = f"{full_response}\n\n{material}"
        history[-1]["content"] = full_response
        response_msg.content = full_response
        await response_msg.update()
    logger.log("assistant", full_response, model=active_model)  # IID-CHAT-LOG
    if sheets_logger:
        sheets_logger.log("assistant", full_response, model=active_model)  # IID-SHEETS-LOG
    # IID-LEARN-DIAGNOSE: this posed question is the fixed "big question" the student keeps
    # re-answering for the rest of this goal; the diagnostic turn references it.
    cl.user_session.set("current_big_question", full_response)
    # IID-LEARN-DIAGNOSE: fresh goal → fresh dialogue transcript for the diagnose call
    cl.user_session.set("goal_dialogue", [])
    await _send_actions(response_msg.id, full_response, mode)


async def _diagnostic_turn(
    history: list[dict], user_text: str, course_llm: dict,
    logger: ChatLogger, sheets_logger: "SheetsLogger | None",
) -> None:
    """IID-LEARN-DIAGNOSE: two-step learning-goals turn — diagnose the answer, then act.

    Step 1 (diagnose): a non-streamed structured call ranks the student's misunderstandings and
    picks the single most important one (shown to the student as a subtle "Analysing…" step).
    Step 2 (act): the existing streamed reply, seeded to address only that one point and re-ask
    the fixed big question. The diagnosis JSON is logged as an internal event (never shown).
    """
    diagnose_prompt: str = cl.user_session.get("diagnose_prompt", "")
    lecture_content: str = cl.user_session.get("lecture_content", "")
    current_goal: dict = cl.user_session.get("current_goal")
    big_question: str = cl.user_session.get("current_big_question", "")
    # IID-LEARN-DIAGNOSE: full student↔tutor exchange for this goal, so the judge sees
    # points the student already made in earlier turns (not just the latest answer)
    goal_dialogue: list = cl.user_session.get("goal_dialogue") or []

    # Step 1 — diagnose (structured, non-streamed) inside a visible thinking step
    async with cl.Step(name="Analysing your answer…", type="tool") as step:
        diagnosis = await diagnose_answer(
            LLM_CLIENT, course_llm, diagnose_prompt, lecture_content,
            current_goal, big_question, user_text, goal_dialogue,
        )
        step.output = diagnosis.rationale or (
            "Looks solid." if diagnosis.mastered else "Identified the main gap."
        )

    # Log the diagnosis internally (IID-CHAT-LOG / IID-SHEETS-LOG) — audit only, not shown
    diag_json = json.dumps(diagnosis.as_dict(), ensure_ascii=False)
    logger.log("diagnosis", diag_json)
    if sheets_logger:
        sheets_logger.log("diagnosis", diag_json)

    # Step 2 — act: seed the streamed reply with the chosen misconception + tactic
    act_instruction = build_act_instruction(diagnosis, big_question)
    history.append({"role": "user", "content": act_instruction})  # internal, not logged
    # IID-LEARN-GOALS: hide reasoning — it spells out the mastery verdict and the answer
    response_msg, full_response, active_model, ok = await _stream_assistant(
        history, course_llm, show_reasoning=False)
    if not ok:
        # IID-STREAM-RESILIENCE: the student's answer never got feedback. Don't record the
        # stall in `goal_dialogue` — the next diagnose call must see the real exchange only,
        # and the student keeps their mastery credit for what they already said.
        _log_stream_failure(logger, sheets_logger, full_response, active_model)
        return
    logger.log("assistant", full_response, model=active_model)  # IID-CHAT-LOG
    if sheets_logger:
        sheets_logger.log("assistant", full_response, model=active_model)  # IID-SHEETS-LOG
    # IID-LEARN-DIAGNOSE: record this exchange so the next diagnose call sees the full dialogue
    goal_dialogue.append({"role": "student", "content": user_text})
    goal_dialogue.append({"role": "tutor", "content": full_response})
    cl.user_session.set("goal_dialogue", goal_dialogue)
    await _send_actions(response_msg.id, full_response, "learning_goals")


def _with_viewer_catalog(system_prompt: str, viewer: ViewerSet | None, mode: str) -> str:
    """IID-UI-CONTENT-MARK: append the linkable-pages catalogue in Q&A mode. Returns the
    prompt object itself when there is nothing to add — a course without HTML gets exactly
    the prompt it had before this feature."""
    if viewer is None or mode != "qa":
        return system_prompt
    return f"{system_prompt}\n{viewer.catalog()}\n"


@cl.on_chat_start
async def on_chat_start() -> None:
    """IID-CHAT-SHELL1, IID-AUTH-BASIC, IID-MULTI-COURSE: Initialise session state."""
    session_id = str(uuid.uuid4())

    # IID-AUTH-BASIC: capture authenticated user email (None when auth is disabled)
    chainlit_user = cl.context.session.user
    user_email = chainlit_user.identifier if chainlit_user else None

    # IID-MULTI-COURSE: resolve course from selected profile, or use root content (fallback)
    if COURSES:
        profile_id = cl.user_session.get("chat_profile")
        course = next((c for c in COURSES if c.lecture_name == profile_id), COURSES[0])
        # IID-MULTI-COURSE: defensive guard — chooser already filters, but a stale
        # browser tab or out-of-window fallback could land here.
        if not course.is_available(date.today()):
            await cl.Message(
                content=f"**{course.lecture_name}** is not available right now. "
                        f"{course.availability_line()}".strip()
            ).send()
            return
        # IID-COURSE-ACCESS: same defensive guard for the per-course login allowlist —
        # the chooser never offers a restricted course, but never trust the client.
        if not course.is_accessible(user_email):
            await cl.Message(
                content=f"**{course.lecture_name}** is not available for your account. "
                        f"Please pick another course from the profile chooser."
            ).send()
            return
        # IID-LEARN-DIAGNOSE: load once and reuse below (learning-goals mode used to read and
        # clean these same files up to 3x per session start — see
        # agent/session_churn_fix_handoff.md)
        course_content = load_course_content(course)
        system_prompt = build_system_prompt(course, content=course_content)
        welcome = load_course_text(course.welcome_path, course.lecture_name)
        course_llm = course.llm
        model_choices = course.student_model_choices  # IID-STUDENT-MODEL-CHOICE
    else:
        # Single-course fallback: load root content/ directly (IID-CONTENT-INJECT)
        content = load_content(_ROOT_CONTENT)
        instructions = load_course_text(
            _ROOT_CONTENT / "_system_prompt.md", CFG.get("course_name", "this course")
        )
        welcome = load_course_text(
            _ROOT_CONTENT / "_welcome.md", CFG.get("course_name", "this course")
        )
        system_prompt = (
            f"{instructions}\n\n"
            f"--- LECTURE CONTENT START ---\n{content}\n--- LECTURE CONTENT END ---\n"
        )
        course_llm = CFG.get("llm", {})
        # IID-STUDENT-MODEL-CHOICE: single-course deploys (content dir with no subfolders,
        # e.g. teachbot-timeseries) read the list straight from the deploy config, since
        # there is no course _meta.yaml to carry it.
        model_choices = _SINGLE_COURSE_MODEL_CHOICES

    course_name = course.lecture_name if COURSES else CFG.get("course_name", "")
    logger = ChatLogger(CFG.get("logs_dir", "logs"), session_id, user_email=user_email, course_name=course_name)

    # IID-SHEETS-LOG: optional persistent Google Sheets logger (disabled when sheets_log_id is blank)
    sheets_id = CFG.get("sheets_log_id", "")
    sheets_logger = SheetsLogger(sheets_id, session_id, user_email=user_email, course_name=course_name) if sheets_id else None

    # IID-STUDENT-MODEL-CHOICE, IID-LLM-THINKING: label → the whole choice, not just the id.
    # A choice carries its own `reasoning` setting, so the same model can appear twice under
    # different labels (with and without chain-of-thought). Empty ⇒ feature off here.
    model_choice_map: dict[str, dict] = {m["label"]: m for m in model_choices}

    # IID-LEARN-GOALS: learning-goals practice mode — load progress, sample one goal,
    # inject ONLY that goal into the system prompt. `current_goal is None` ⇒ all goals done.
    mode = course.mode if COURSES else "qa"

    # IID-UI-CONTENT-VIEW, IID-UI-CONTENT-MARK: HTML documents next to the chat. In Q&A mode
    # the bot also gets their catalogue (static → part of the cached system prompt) so it can
    # link slides and cards. Learning-goals mode shows the panel but keeps its own prompt.
    viewer: ViewerSet | None = course.viewer if COURSES else ROOT_VIEWER
    system_prompt = _with_viewer_catalog(system_prompt, viewer, mode)

    progress_store: ProgressStore | None = None
    current_goal: dict | None = None
    completed: set[str] = set()
    if mode == "learning_goals":
        progress_store = ProgressStore(sheets_id, user_email, course_name)
        completed = await progress_store.completed_goal_ids()
        current_goal = sample_goal(course.learning_goals, completed)
        if current_goal is not None:
            # IID-COST-CACHE: block form — stable lecture-content block cached across goals.
            # Reuse course_content computed above instead of re-reading the files.
            system_prompt = build_goal_system_blocks(course, current_goal, base=system_prompt)
        # IID-LEARN-DIAGNOSE: cache the diagnose prompt + lecture content once so the two-step
        # turn (diagnose → act) needn't re-read them on every student answer. Reuses
        # course_content computed above instead of a third redundant file read.
        cl.user_session.set(
            "diagnose_prompt",
            load_course_text(course.diagnose_prompt_path, course.lecture_name)
            if course.diagnose_prompt_path else "",
        )
        cl.user_session.set("lecture_content", course_content)

    # Store in Chainlit user session
    cl.user_session.set("history", [{"role": "system", "content": system_prompt}])
    cl.user_session.set("mode", mode)  # IID-LEARN-GOALS
    cl.user_session.set("progress_store", progress_store)  # IID-LEARN-GOALS
    cl.user_session.set("current_goal", current_goal)  # IID-LEARN-GOALS
    cl.user_session.set("completed", completed)  # IID-LEARN-GOALS
    if COURSES:
        cl.user_session.set("course", course)  # IID-LEARN-GOALS: needed to sample the next goal
    cl.user_session.set("logger", logger)
    cl.user_session.set("sheets_logger", sheets_logger)
    # IID-MULTI-COURSE, IID-STUDENT-MODEL-CHOICE: per-session LLM config — a *copy*, because
    # `course.llm` / `CFG["llm"]` are shared across every session in the process. Without the
    # copy, one student picking a model (or a reasoning setting) would change it for everyone.
    cl.user_session.set("course_llm", dict(course_llm))
    cl.user_session.set("model_choice_map", model_choice_map)  # IID-STUDENT-MODEL-CHOICE
    cl.user_session.set("viewer", viewer)  # IID-UI-CONTENT-VIEW
    cl.user_session.set("viewer_state", {"open": False, "doc": "", "loc": ""})  # IID-UI-CONTENT-CONTEXT

    # IID-STUDENT-MODEL-CHOICE: show model selector when the course defines choices
    if model_choice_map:
        # IID-LLM-THINKING: match on model *and* reasoning — with two choices sharing one
        # model id, matching on the id alone would preselect the wrong label.
        current = (course_llm.get("model", ""), _reasoning_of(course_llm))
        current_label = next(
            (lbl for lbl, c in model_choice_map.items()
             if (c["id"], _reasoning_of(c)) == current),
            next(iter(model_choice_map)),
        )
        await cl.ChatSettings([
            Select(id="model", label="LLM Model",
                   values=list(model_choice_map.keys()),
                   initial_value=current_label)
        ]).send()

    # IID-UI-CONTENT-VIEW: tell public/viewer.js whether this course has documents — it
    # shows/hides the header button and opens the panel on wide screens.
    await cl.send_window_message({
        "type": "lectos_viewer_available", "count": len(viewer.docs) if viewer else 0,
        "word": viewer.button_word() if viewer else "",
    })
    await cl.Message(content=welcome).send()  # IID-CHAT-SHELL1, IID-EDUCATOR-CONFIG

    # IID-LEARN-GOALS: in learning-goals mode, either announce completion or pose the first question
    if mode == "learning_goals":
        if current_goal is None:
            await cl.Message(
                content="🎉 You have completed all learning goals for this course. "
                        "Nothing left to practice — well done!"
            ).send()
            return
        history = cl.user_session.get("history")
        await _pose_goal_question(history, course_llm, logger, sheets_logger, mode)


def _reasoning_of(d: dict) -> object:
    """IID-LLM-THINKING: a config's reasoning setting, or None when it leaves it to the
    provider. Used to compare a live LLM config against a model choice."""
    return d.get("reasoning")


@cl.on_settings_update
async def on_settings_update(settings: dict) -> None:
    """IID-STUDENT-MODEL-CHOICE, IID-LLM-THINKING: apply the student's choice to the session.

    A choice fully defines model *and* reasoning: picking one that omits `reasoning` clears
    any previously-applied setting, so switching "no thinking" → "with thinking" and back
    lands on the intended state both ways instead of latching the first one chosen.
    """
    model_choice_map: dict = cl.user_session.get("model_choice_map", {})
    choice = model_choice_map.get(settings.get("model"))
    if not choice:
        return
    course_llm: dict = cl.user_session.get("course_llm")
    course_llm["model"] = choice["id"]
    if "reasoning" in choice:
        course_llm["reasoning"] = choice["reasoning"]
    else:
        course_llm.pop("reasoning", None)
    cl.user_session.set("course_llm", course_llm)


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """IID-QNA-CORE, IID-UI-RENDER: Handle student question, stream answer."""
    history: list[dict] = cl.user_session.get("history")
    logger: ChatLogger = cl.user_session.get("logger")
    sheets_logger: SheetsLogger | None = cl.user_session.get("sheets_logger")
    course_llm: dict = cl.user_session.get("course_llm")  # IID-MULTI-COURSE
    mode: str = cl.user_session.get("mode", "qa")  # IID-LEARN-GOALS

    # IID-PUBLIC-RATELIMIT: enforce per-session caps before any logging or LLM call
    if _LIMITS:
        max_chars = _LIMITS.get("max_message_chars")
        if max_chars and len(message.content) > max_chars:
            await cl.Message(
                content=f"⚠️ Please keep messages under {max_chars} characters."
            ).send()
            return
        max_turns = _LIMITS.get("max_turns_per_session")
        if max_turns:
            turns = cl.user_session.get("turn_count", 0) + 1
            cl.user_session.set("turn_count", turns)
            if turns > max_turns:
                await cl.Message(
                    content="⚠️ This session has reached its message limit. "
                            "Please come back later to continue."
                ).send()
                return

    user_text = message.content.strip()

    # IID-UI-CONTENT-CONTEXT: the page open in the viewer panel goes into this request only;
    # the history keeps a one-line marker of it. Q&A mode only — learning-goals turns are
    # driven by the goal, not by whatever page happens to be open.
    viewer: ViewerSet | None = cl.user_session.get("viewer")
    page_context: str | None = None
    viewer_tag: str | None = None
    stored_text = user_text
    if viewer is not None and mode == "qa":
        state = cl.user_session.get("viewer_state") or {}
        open_page = viewer.validate(state.get("doc"), state.get("loc")) if state.get("open") else None
        if open_page:
            page_context = viewer.page_context(*open_page)
            viewer_tag = viewer.tag(*open_page)
            stored_text = f"{viewer.marker(*open_page)}\n{user_text}"

    history.append({"role": "user", "content": stored_text})
    logger.log("user", user_text, viewer=viewer_tag)  # IID-CHAT-LOG
    if sheets_logger:
        sheets_logger.log("user", user_text, viewer=viewer_tag)  # IID-SHEETS-LOG

    # IID-LEARN-DIAGNOSE: in learning-goals mode, each answer is a two-step diagnose→act turn.
    # Guarded by an active goal (None ⇒ all goals done, fall through to a plain reply).
    if mode == "learning_goals" and cl.user_session.get("current_goal") is not None:
        # IID-STREAM-RESILIENCE: an empty big question means the opening question itself
        # stalled (see `_pose_goal_question`). Re-pose it instead of diagnosing an answer
        # to a question the student was never shown.
        if not cl.user_session.get("current_big_question"):
            history.pop()  # the student's message is a retry trigger, not an answer
            await _pose_goal_question(history, course_llm, logger, sheets_logger, mode)
            return
        await _diagnostic_turn(history, user_text, course_llm, logger, sheets_logger)
        return

    # Stream response — IID-UI-RENDER (Chainlit renders MD + LaTeX natively)
    response_msg, full_response, active_model, ok = await _stream_assistant(
        history, course_llm, page_context=page_context)
    if not ok:  # IID-STREAM-RESILIENCE: every attempt stalled — history already rewound
        _log_stream_failure(logger, sheets_logger, full_response, active_model)
        return
    # IID-UI-CONTENT-MARK: `[t](view:DOC/LOC)` → links that open the page in the panel.
    # Done once streaming has finished; history and logs keep the model's own wording.
    if viewer is not None:
        shown = viewer.rewrite_links(full_response)
        if shown != full_response:
            response_msg.content = shown
            await response_msg.update()
    logger.log("assistant", full_response, model=active_model)  # IID-CHAT-LOG, IID-STUDENT-MODEL-CHOICE
    if sheets_logger:
        sheets_logger.log("assistant", full_response, model=active_model)  # IID-SHEETS-LOG, IID-STUDENT-MODEL-CHOICE

    # IID-STUDENT-FEEDBACK-STORE + IID-LEARN-GOALS: flag button (+ goal-complete button in goals mode)
    await _send_actions(response_msg.id, full_response, mode)


# IID-UI-CONTENT-VIEW: key of the viewer panel in Chainlit's element sidebar. Re-sending
# elements under the same key while the panel is open is a no-op on the client, so "open"
# can be sent unconditionally without reloading a 7 MB deck the student is reading.
_VIEWER_KEY = "lectos-viewer"


async def _open_viewer(viewer: ViewerSet, target: tuple[str, str] | None) -> None:
    """IID-UI-CONTENT-VIEW: open the panel at `target`, else where the student last was."""
    state = cl.user_session.get("viewer_state") or {}
    if target is None:
        target = viewer.validate(state.get("doc"), state.get("loc")) or viewer.default_target()
    element = cl.CustomElement(
        name="HtmlViewer",  # public/elements/HtmlViewer.jsx
        props={"docs": viewer.client_docs(), "start": viewer.url(*target)},
    )
    # Title "canvas" = Chainlit's full-bleed side view: 50% width, no padding, no title bar
    # (only its close button). Set before the elements: setting a title drops the key.
    await cl.ElementSidebar.set_title("canvas")
    # Not `cl.ElementSidebar.set_elements`: it first sends the element into the chat's
    # element list, and the client resets the side view whenever that list changes (losing
    # the "canvas" title) — and it writes a file per open under .files/. A custom element
    # carries everything in its props, so the sidebar event alone is enough. Same event
    # and payload as chainlit/sidebar.py (2.11.0); tests/content_view.py pins this.
    await cl.context.emitter.emit(
        "set_sidebar_elements", {"elements": [element.to_dict()], "key": _VIEWER_KEY}
    )


@cl.on_window_message
async def on_window_message(data: object) -> None:
    """IID-UI-CONTENT-VIEW, IID-UI-CONTENT-CONTEXT, IID-UI-CONTENT-MARK: viewer events.

    Chainlit forwards every `postMessage` the chat window receives, from any sender — so
    each payload is validated against this session's indexed documents, and anything
    unknown is ignored. Senders: public/elements/HtmlViewer.jsx (panel state) and
    public/viewer.js (header button, clicks on viewer links in answers).
    """
    viewer: ViewerSet | None = cl.user_session.get("viewer")
    if viewer is None or not isinstance(data, dict):
        return
    kind = data.get("type")
    state: dict = cl.user_session.get("viewer_state") or {"open": False, "doc": "", "loc": ""}
    if kind == "lectos_viewer_state":
        if not data.get("open"):
            state["open"] = False
        else:
            page = viewer.validate(data.get("doc"), data.get("loc"))
            if page:
                state.update(open=True, doc=page[0], loc=page[1])
        cl.user_session.set("viewer_state", state)
    elif kind == "lectos_viewer_open":
        await _open_viewer(viewer, viewer.parse_href(data.get("href")))
    elif kind == "lectos_viewer_close":
        state["open"] = False
        cl.user_session.set("viewer_state", state)
        await cl.ElementSidebar.set_elements([])


@cl.action_callback("complete_goal")
async def on_complete_goal(action: cl.Action) -> None:
    """IID-LEARN-GOALS: record the current goal as done and advance to the next one."""
    progress_store: ProgressStore | None = cl.user_session.get("progress_store")
    current_goal: dict | None = cl.user_session.get("current_goal")
    completed: set[str] = cl.user_session.get("completed", set())
    course: CourseConfig | None = cl.user_session.get("course")
    logger: ChatLogger = cl.user_session.get("logger")
    sheets_logger: SheetsLogger | None = cl.user_session.get("sheets_logger")
    course_llm: dict = cl.user_session.get("course_llm")

    if current_goal is None or course is None:
        return  # stale button (e.g. all goals already completed)

    # IID-LEARN-GOALS: a button from an earlier goal (or a double-click) must not
    # complete the current goal — completions cannot be undone by re-clicking.
    if action.payload.get("goal_id") != current_goal["id"]:
        await cl.Message(
            content="That button belongs to a goal you already recorded — completions "
                    "can't be undone. You're now working on the goal above."
        ).send()
        return

    # Persist completion and exclude this goal from further sampling
    if progress_store is not None:
        progress_store.mark_done(current_goal["id"])  # IID-LEARN-GOALS
    completed.add(current_goal["id"])
    cl.user_session.set("completed", completed)

    next_goal = sample_goal(course.learning_goals, completed)
    if next_goal is None:
        cl.user_session.set("current_goal", None)
        await cl.Message(
            content="✅ Recorded. 🎉 That was the last goal — you've completed every learning "
                    "goal for this course. Well done!"
        ).send()
        return

    # Reset context to the next goal so only one goal is ever in the LLM's context
    # IID-COST-CACHE: block form — the lecture-content block stays cached across the goal switch
    cl.user_session.set("current_goal", next_goal)
    new_prompt = build_goal_system_blocks(course, next_goal)
    history = [{"role": "system", "content": new_prompt}]
    cl.user_session.set("history", history)

    await cl.Message(content="✅ Recorded. Here's your next goal:").send()
    await _pose_goal_question(history, course_llm, logger, sheets_logger, "learning_goals")


@cl.action_callback("flag")
async def on_flag(action: cl.Action) -> None:
    """IID-STUDENT-FEEDBACK-STORE: collect and store student feedback on a flagged AI response."""
    logger: ChatLogger = cl.user_session.get("logger")
    sheets_logger: SheetsLogger | None = cl.user_session.get("sheets_logger")

    res = await cl.AskUserMessage(
        content="What's wrong with this response? (describe the issue)",
        timeout=3600,
    ).send()
    if not res:
        return
    comment = res["output"].strip()

    flagged_message = action.payload.get("flagged_message", "")
    logger.log_feedback(flagged_message=flagged_message, student_comment=comment)
    if sheets_logger:
        sheets_logger.log_feedback(flagged_message=flagged_message, student_comment=comment)

    await cl.Message(content="Thanks — your feedback has been recorded.").send()
