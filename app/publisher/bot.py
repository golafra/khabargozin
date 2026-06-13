"""Telegram bot wrapper."""

import asyncio
from typing import Optional

from app.config import get_settings
from app.db.models.audit_log import AppState
from app.db.session import get_session
from app.publisher.telegram_retry import publish_with_retry


def resolve_chat_id(mode: str) -> str:
    settings = get_settings()
    if mode == "test":
        return settings.TEST_OUTPUT_CHANNEL_ID
    if mode == "production":
        return settings.PRODUCTION_OUTPUT_CHANNEL_ID
    return ""


def get_cached_chat_id(mode: str) -> Optional[str]:
    session = get_session()
    try:
        row = session.get(AppState, f"telegram_chat_id:{mode}")
        return row.value if row else None
    finally:
        session.close()


def cache_chat_id(mode: str, chat_id: str) -> None:
    session = get_session()
    try:
        row = session.get(AppState, f"telegram_chat_id:{mode}")
        if row:
            row.value = chat_id
        else:
            session.add(AppState(key=f"telegram_chat_id:{mode}", value=chat_id))
        session.commit()
    finally:
        session.close()


def send_message_html(chat_id: str, text: str) -> int:
    settings = get_settings()
    if not settings.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not configured")

    from telegram import Bot

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

    def _send():
        return asyncio.run(
            bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=settings.TELEGRAM_PARSE_MODE,
                disable_web_page_preview=True,
            )
        )

    message = publish_with_retry(_send)
    return message.message_id


def edit_message_html(chat_id: str, message_id: int, text: str) -> None:
    settings = get_settings()
    from telegram import Bot

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

    def _edit():
        return asyncio.run(
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode=settings.TELEGRAM_PARSE_MODE,
                disable_web_page_preview=True,
            )
        )

    publish_with_retry(_edit)
