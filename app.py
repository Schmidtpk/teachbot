"""
IID-CHAT-SHELL1, IID-QNA-CORE, IID-UI-RENDER, IID-AUTH-BASIC, IID-STUDENT-FEEDBACK-STORE,
IID-MULTI-COURSE
Chainlit entry point for Lectos v1.
Run with:  chainlit run app.py
"""

import json
import uuid
from datetime import date
from pathlib import Path
from typing import Optional

import chainlit as cl
from chainlit.input_widget import Select
import yaml
from dotenv import load_dotenv

from src.auth import auth_enabled, find_user, is_email_allowed, is_valid_email, load_users, register_user, verify_password
from src.chat_logger import ChatLogger, SheetsLogger
from src.content_loader import load_content
from src.course_loader import CourseConfig, build_system_prompt, discover_courses, load_course_text
from src.goals import GOAL_KICKOFF, build_goal_system_blocks, goal_material, sample_goal
from src.llm_client import build_client, stream_response
from src.progress_store import ProgressStore
from src.tutor_loop import build_act_instruction, diagnose_answer

# SID-API-CONFIG: load secrets from .env (never hardcoded)
load_dotenv()

# Load educator config — IID-EDUCATOR-CONFIG, SID-API-CONFIG
_cfg_path = Path(__file__).parent / "config.yaml"
with _cfg_path.open(encoding="utf-8") as fh:
    CFG: dict = yaml.safe_load(fh)

# IID-LLM-PROVIDER: single shared async client (model overrides flow through cfg, not the client)
LLM_CLIENT = build_client(CFG)

# IID-MULTI-COURSE: discover course subfolders at startup; [] = single-course fallback mode
_ROOT_CONTENT = Path(CFG.get("content_dir", "content"))
COURSES: list[CourseConfig] = discover_courses(_ROOT_CONTENT, CFG)


_AUTH_CFG = CFG.get("auth", {})


@cl.set_chat_profiles
async def set_chat_profiles(user: cl.User | None) -> list[cl.ChatProfile] | None:
    """IID-MULTI-COURSE: Expose course subfolders as Chainlit chat profiles.

    Returns None when no subfolders exist, suppressing the profile chooser and
    preserving single-course behavior. Courses outside their `first_date`/`last_date`
    window in `_meta.yaml` are filtered out. If COURSES is non-empty but every course
    is currently out of window, returns [] (empty chooser) rather than None — falling
    back to single-course mode would silently load root content/, which is wrong.
    """
    if not COURSES:
        return None
    today = date.today()
    visible = [c for c in COURSES if c.is_available(today)]
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


async def _stream_assistant(history: list[dict], course_llm: dict) -> tuple[cl.Message, str, str]:
    """IID-QNA-CORE, IID-UI-RENDER: Stream one assistant turn, append it to history.

    Returns (message, full_response, active_model). Caller is responsible for logging.
    """
    active_model = course_llm.get("model", "")  # IID-STUDENT-MODEL-CHOICE
    response_msg = cl.Message(content="")
    await response_msg.send()

    full_response = ""
    async for token in stream_response(LLM_CLIENT, {"llm": course_llm}, history):
        full_response += token
        await response_msg.stream_token(token)
    await response_msg.update()

    history.append({"role": "assistant", "content": full_response})
    return response_msg, full_response, active_model


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
    response_msg, full_response, active_model = await _stream_assistant(history, course_llm)
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
    response_msg, full_response, active_model = await _stream_assistant(history, course_llm)
    logger.log("assistant", full_response, model=active_model)  # IID-CHAT-LOG
    if sheets_logger:
        sheets_logger.log("assistant", full_response, model=active_model)  # IID-SHEETS-LOG
    # IID-LEARN-DIAGNOSE: record this exchange so the next diagnose call sees the full dialogue
    goal_dialogue.append({"role": "student", "content": user_text})
    goal_dialogue.append({"role": "tutor", "content": full_response})
    cl.user_session.set("goal_dialogue", goal_dialogue)
    await _send_actions(response_msg.id, full_response, "learning_goals")


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
        system_prompt = build_system_prompt(course)
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
        model_choices = []  # IID-STUDENT-MODEL-CHOICE: not supported in single-course fallback

    course_name = course.lecture_name if COURSES else CFG.get("course_name", "")
    logger = ChatLogger(CFG.get("logs_dir", "logs"), session_id, user_email=user_email, course_name=course_name)

    # IID-SHEETS-LOG: optional persistent Google Sheets logger (disabled when sheets_log_id is blank)
    sheets_id = CFG.get("sheets_log_id", "")
    sheets_logger = SheetsLogger(sheets_id, session_id, user_email=user_email, course_name=course_name) if sheets_id else None

    # IID-STUDENT-MODEL-CHOICE: build label→id map; empty when feature is off for this course
    model_choice_map: dict[str, str] = {m["label"]: m["id"] for m in model_choices}

    # IID-LEARN-GOALS: learning-goals practice mode — load progress, sample one goal,
    # inject ONLY that goal into the system prompt. `current_goal is None` ⇒ all goals done.
    mode = course.mode if COURSES else "qa"
    progress_store: ProgressStore | None = None
    current_goal: dict | None = None
    completed: set[str] = set()
    if mode == "learning_goals":
        progress_store = ProgressStore(sheets_id, user_email, course_name)
        completed = await progress_store.completed_goal_ids()
        # IID-LEARN-GOALS: stable per-student seed so a page reload (iPad Safari evicts
        # the tab on app switch → new Chainlit session) re-serves the SAME goal instead
        # of a freshly randomised one. None (auth disabled) ⇒ random per session.
        goal_seed = f"{user_email}:{course_name}" if user_email else None
        cl.user_session.set("goal_seed", goal_seed)
        current_goal = sample_goal(course.learning_goals, completed, seed_key=goal_seed)
        if current_goal is not None:
            # IID-COST-CACHE: block form — stable lecture-content block cached across goals
            system_prompt = build_goal_system_blocks(course, current_goal)
        # IID-LEARN-DIAGNOSE: cache the diagnose prompt + lecture content once so the two-step
        # turn (diagnose → act) needn't re-read them on every student answer.
        cl.user_session.set(
            "diagnose_prompt",
            load_course_text(course.diagnose_prompt_path, course.lecture_name)
            if course.diagnose_prompt_path else "",
        )
        cl.user_session.set("lecture_content", load_content(course.content_dir))

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
    cl.user_session.set("course_llm", course_llm)  # IID-MULTI-COURSE: per-session LLM config
    cl.user_session.set("model_choice_map", model_choice_map)  # IID-STUDENT-MODEL-CHOICE

    # IID-STUDENT-MODEL-CHOICE: show model selector when the course defines choices
    if model_choice_map:
        current_model = course_llm.get("model", "")
        current_label = next(
            (lbl for lbl, mid in model_choice_map.items() if mid == current_model),
            next(iter(model_choice_map)),
        )
        await cl.ChatSettings([
            Select(id="model", label="LLM Model",
                   values=list(model_choice_map.keys()),
                   initial_value=current_label)
        ]).send()

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


@cl.on_settings_update
async def on_settings_update(settings: dict) -> None:
    """IID-STUDENT-MODEL-CHOICE: Apply student-selected model to session LLM config."""
    model_choice_map: dict = cl.user_session.get("model_choice_map", {})
    model_id = model_choice_map.get(settings.get("model"))
    if model_id:
        course_llm: dict = cl.user_session.get("course_llm")
        course_llm["model"] = model_id
        cl.user_session.set("course_llm", course_llm)


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """IID-QNA-CORE, IID-UI-RENDER: Handle student question, stream answer."""
    history: list[dict] = cl.user_session.get("history")
    logger: ChatLogger = cl.user_session.get("logger")
    sheets_logger: SheetsLogger | None = cl.user_session.get("sheets_logger")
    course_llm: dict = cl.user_session.get("course_llm")  # IID-MULTI-COURSE
    mode: str = cl.user_session.get("mode", "qa")  # IID-LEARN-GOALS

    user_text = message.content.strip()
    history.append({"role": "user", "content": user_text})
    logger.log("user", user_text)  # IID-CHAT-LOG
    if sheets_logger:
        sheets_logger.log("user", user_text)  # IID-SHEETS-LOG

    # IID-LEARN-DIAGNOSE: in learning-goals mode, each answer is a two-step diagnose→act turn.
    # Guarded by an active goal (None ⇒ all goals done, fall through to a plain reply).
    if mode == "learning_goals" and cl.user_session.get("current_goal") is not None:
        await _diagnostic_turn(history, user_text, course_llm, logger, sheets_logger)
        return

    # Stream response — IID-UI-RENDER (Chainlit renders MD + LaTeX natively)
    response_msg, full_response, active_model = await _stream_assistant(history, course_llm)
    logger.log("assistant", full_response, model=active_model)  # IID-CHAT-LOG, IID-STUDENT-MODEL-CHOICE
    if sheets_logger:
        sheets_logger.log("assistant", full_response, model=active_model)  # IID-SHEETS-LOG, IID-STUDENT-MODEL-CHOICE

    # IID-STUDENT-FEEDBACK-STORE + IID-LEARN-GOALS: flag button (+ goal-complete button in goals mode)
    await _send_actions(response_msg.id, full_response, mode)


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

    # IID-LEARN-GOALS: same deterministic seed as on_chat_start — the enlarged completed
    # set changes the pick, so the next goal varies while staying reload-stable.
    next_goal = sample_goal(course.learning_goals, completed, seed_key=cl.user_session.get("goal_seed"))
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
