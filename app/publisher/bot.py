"""Telegram bot wrapper."""

import asyncio
from typing import Optional

from app.config import get_settings
from app.db.models.audit_log import AppState
from app.db.session import get_session
from app.publisher.telegram_retry import publish_with_retry


def resolve_chat_id(mode: str) -> str:
    settings = get_settings()
    cached = get_cached_chat_id(mode)
    if cached:
        return cached
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
            row.value = str(chat_id)
        else:
            session.add(AppState(key=f"telegram_chat_id:{mode}", value=str(chat_id)))
        session.commit()
    finally:
        session.close()


def _get_bot():
    from telegram import Bot

    settings = get_settings()
    if not settings.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not configured")
    return Bot(token=settings.TELEGRAM_BOT_TOKEN)


def resolve_and_cache_chat(mode: str) -> str:
    """Resolve @username to numeric chat_id via getChat and cache it."""
    cached = get_cached_chat_id(mode)
    if cached and cached.lstrip("-").isdigit():
        return cached

    settings = get_settings()
    username = (
        settings.TEST_OUTPUT_CHANNEL_ID
        if mode == "test"
        else settings.PRODUCTION_OUTPUT_CHANNEL_ID
    )
    if not username:
        raise RuntimeError(f"No channel configured for mode={mode}")

    bot = _get_bot()

    async def _resolve():
        chat = await bot.get_chat(username)
        return str(chat.id)

    chat_id = asyncio.run(_resolve())
    cache_chat_id(mode, chat_id)
    return chat_id


def _effective_chat_id(mode: str) -> str:
    settings = get_settings()
    if settings.PUBLISH_MODE == "dry_run":
        return ""
    try:
        return resolve_and_cache_chat(mode)
    except Exception:
        return resolve_chat_id(mode)


def send_message_html(chat_id: str | None = None, text: str = "", *, mode: str | None = None) -> int:
    settings = get_settings()
    if mode is None:
        mode = settings.PUBLISH_MODE
    target = chat_id or _effective_chat_id(mode)
    if not target:
        raise RuntimeError("No chat_id resolved for publish")

    bot = _get_bot()

    def _send():
        return asyncio.run(
            bot.send_message(
                chat_id=target,
                text=text,
                parse_mode=settings.TELEGRAM_PARSE_MODE,
                disable_web_page_preview=True,
            )
        )

    message = publish_with_retry(_send)
    return message.message_id


def edit_message_html(chat_id: str, message_id: int, text: str) -> None:
    settings = get_settings()
    bot = _get_bot()

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
