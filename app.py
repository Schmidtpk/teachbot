"""
IID-CHAT-SHELL1, IID-QNA-CORE, IID-UI-RENDER
Chainlit entry point for teachbot v1.
Run with:  chainlit run app.py
"""

import uuid
from pathlib import Path

import chainlit as cl
import yaml
from dotenv import load_dotenv

from src.chat_logger import ChatLogger, SheetsLogger
from src.content_loader import load_content
from src.llm_client import build_client, stream_response

# SID-API-CONFIG: load secrets from .env (never hardcoded)
load_dotenv()

# Load educator config — IID-EDUCATOR-CONFIG, SID-API-CONFIG
_cfg_path = Path(__file__).parent / "config.yaml"
with _cfg_path.open(encoding="utf-8") as fh:
    CFG: dict = yaml.safe_load(fh)

# IID-CONTENT-INJECT: load and cache content at startup
COURSE_CONTENT: str = load_content(CFG.get("content_dir", "content"))

# IID-LLM-PROVIDER: single shared async client
LLM_CLIENT = build_client(CFG)

SYSTEM_PROMPT = f"""\
You are a helpful teaching assistant for the course "{CFG.get('course_name', 'this course')}".

Your role is to answer student questions accurately based solely on the lecture content provided below.
- Answer in clear, concise Markdown. Use math notation ($...$ or $$...$$) where appropriate.
- Cite or paraphrase the relevant lecture material in your answer.
- If a question is not covered by the lecture content, say so honestly and do not invent information.
- Politely decline requests unrelated to the course.

--- LECTURE CONTENT START ---
{COURSE_CONTENT}
--- LECTURE CONTENT END ---
"""


@cl.on_chat_start
async def on_chat_start() -> None:
    """IID-CHAT-SHELL1: Initialise session state."""
    session_id = str(uuid.uuid4())
    logger = ChatLogger(CFG.get("logs_dir", "logs"), session_id)

    # IID-SHEETS-LOG: optional persistent Google Sheets logger (disabled when sheets_log_id is blank)
    sheets_id = CFG.get("sheets_log_id", "")
    sheets_logger = SheetsLogger(sheets_id, session_id) if sheets_id else None

    # Store in Chainlit user session
    cl.user_session.set("history", [{"role": "system", "content": SYSTEM_PROMPT}])
    cl.user_session.set("logger", logger)
    cl.user_session.set("sheets_logger", sheets_logger)

    await cl.Message(
        content=(
            f"**Welcome to the {CFG.get('course_name', 'course')} assistant!**\n\n"
            "Ask me anything about the lecture material."
        )
    ).send()


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
    async for token in stream_response(LLM_CLIENT, CFG, history):
        full_response += token
        await response_msg.stream_token(token)

    await response_msg.update()

    history.append({"role": "assistant", "content": full_response})
    logger.log("assistant", full_response)  # IID-CHAT-LOG
    if sheets_logger:
        sheets_logger.log("assistant", full_response)  # IID-SHEETS-LOG
