"""
IID-CHAT-SHELL1, IID-QNA-CORE, IID-UI-RENDER, IID-AUTH-BASIC, IID-STUDENT-FEEDBACK-STORE,
IID-MULTI-COURSE
Chainlit entry point for teachbot v1.
Run with:  chainlit run app.py
"""

import uuid
from pathlib import Path
from typing import Optional

import chainlit as cl
import yaml
from dotenv import load_dotenv

from src.auth import auth_enabled, find_user, is_email_allowed, is_valid_email, load_users, register_user, verify_password
from src.chat_logger import ChatLogger, SheetsLogger
from src.content_loader import load_content
from src.course_loader import CourseConfig, build_system_prompt, discover_courses, load_course_text
from src.llm_client import build_client, stream_response

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
    preserving single-course behavior.
    """
    if not COURSES:
        return None
    return [
        cl.ChatProfile(
            name=course.lecture_name,
            markdown_description=course.description or f"**{course.lecture_name}**",
            default=(i == 0),
        )
        for i, course in enumerate(COURSES)
    ]


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
        system_prompt = build_system_prompt(course)
        welcome = load_course_text(course.welcome_path, course.lecture_name)
        course_llm = course.llm
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

    logger = ChatLogger(CFG.get("logs_dir", "logs"), session_id, user_email=user_email)

    # IID-SHEETS-LOG: optional persistent Google Sheets logger (disabled when sheets_log_id is blank)
    sheets_id = CFG.get("sheets_log_id", "")
    sheets_logger = SheetsLogger(sheets_id, session_id, user_email=user_email) if sheets_id else None

    # Store in Chainlit user session
    cl.user_session.set("history", [{"role": "system", "content": system_prompt}])
    cl.user_session.set("logger", logger)
    cl.user_session.set("sheets_logger", sheets_logger)
    cl.user_session.set("course_llm", course_llm)  # IID-MULTI-COURSE: per-session LLM config

    await cl.Message(content=welcome).send()  # IID-CHAT-SHELL1, IID-EDUCATOR-CONFIG


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """IID-QNA-CORE, IID-UI-RENDER: Handle student question, stream answer."""
    history: list[dict] = cl.user_session.get("history")
    logger: ChatLogger = cl.user_session.get("logger")
    sheets_logger: SheetsLogger | None = cl.user_session.get("sheets_logger")

    user_text = message.content.strip()
    history.append({"role": "user", "content": user_text})
    logger.log("user", user_text)  # IID-CHAT-LOG
    if sheets_logger:
        sheets_logger.log("user", user_text)  # IID-SHEETS-LOG

    # Stream response — IID-UI-RENDER (Chainlit renders MD + LaTeX natively)
    response_msg = cl.Message(content="")
    await response_msg.send()

    full_response = ""
    course_llm: dict = cl.user_session.get("course_llm")  # IID-MULTI-COURSE
    async for token in stream_response(LLM_CLIENT, {"llm": course_llm}, history):
        full_response += token
        await response_msg.stream_token(token)

    await response_msg.update()

    history.append({"role": "assistant", "content": full_response})
    logger.log("assistant", full_response)  # IID-CHAT-LOG
    if sheets_logger:
        sheets_logger.log("assistant", full_response)  # IID-SHEETS-LOG

    # IID-STUDENT-FEEDBACK-STORE: send flag button linked to this message
    await cl.Action(
        name="flag",
        label="🚩 Flag this response",
        payload={"flagged_message": full_response},
    ).send(for_id=response_msg.id)


@cl.action_callback("flag")
async def on_flag(action: cl.Action) -> None:
    """IID-STUDENT-FEEDBACK-STORE: collect and store student feedback on a flagged AI response."""
    logger: ChatLogger = cl.user_session.get("logger")
    sheets_logger: SheetsLogger | None = cl.user_session.get("sheets_logger")

    res = await cl.AskUserMessage(
        content="What's wrong with this response? (describe the issue)",
        timeout=120,
    ).send()
    comment = res["output"].strip() if res else "(no comment)"

    flagged_message = action.payload.get("flagged_message", "")
    logger.log_feedback(flagged_message=flagged_message, student_comment=comment)
    if sheets_logger:
        sheets_logger.log_feedback(flagged_message=flagged_message, student_comment=comment)

    await cl.Message(content="Thanks — your feedback has been recorded.").send()
