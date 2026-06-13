"""Outbox reconciliation against Telegram channel."""

import hashlib
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models.publication import Publication
from app.db.models.publication_outbox import PublicationOutbox
from app.publisher.bot import get_cached_chat_id, resolve_and_cache_chat


def _normalize_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


async def _fetch_recent_channel_messages(chat_id: str, limit: int = 50) -> list[dict]:
    """Read recent posts from the OUTPUT channel (test/production), not source channels.

    Source news is fetched via ICA (FetcherBackend). This helper is only used by
    reconcile_unknown_outbox to match stuck outbox rows against what the bot posted.
    """
    from telegram import Bot

    settings = get_settings()
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    # Bot API limitation: get_updates only sees channel_post updates for the output channel.
    messages = []
    try:
        updates = await bot.get_updates(limit=100)
        for upd in updates:
            msg = upd.channel_post or upd.message
            if msg and str(msg.chat_id) == str(chat_id).lstrip("@"):
                messages.append({
                    "message_id": msg.message_id,
                    "text": msg.text or msg.caption or "",
                })
    except Exception:
        pass
    return messages[-limit:]


def reconcile_unknown_outbox(session: Session, *, apply: bool = False) -> list[dict]:
    """Match unknown outbox items by rendered_text_hash or headline prefix."""
    import asyncio

    settings = get_settings()
    mode = settings.PUBLISH_MODE
    if mode == "dry_run":
        return []

    chat_id = get_cached_chat_id(mode) or resolve_and_cache_chat(mode)
    unknowns = session.query(PublicationOutbox).filter_by(status="unknown").all()
    results = []

    try:
        recent = asyncio.run(_fetch_recent_channel_messages(chat_id))
    except Exception:
        recent = []

    for item in unknowns:
        matched_id: Optional[int] = None
        preview = item.payload_preview or ""
        preview_hash = _hash_text(preview)
        preview_prefix = _normalize_text(preview[:80])

        for msg in recent:
            msg_text = msg.get("text", "")
            if _hash_text(msg_text) == preview_hash:
                matched_id = msg["message_id"]
                break
            if preview_prefix and _normalize_text(msg_text[:80]) == preview_prefix:
                matched_id = msg["message_id"]
                break

        result = {
            "outbox_id": item.id,
            "cluster_id": item.cluster_id,
            "matched": matched_id is not None,
            "telegram_post_id": matched_id,
        }
        results.append(result)

        if apply and matched_id:
            item.status = "sent"
            item.error_message = None
            pub = Publication(
                cluster_id=item.cluster_id,
                outbox_id=item.id,
                telegram_post_id=matched_id,
                track=item.track,
                published_at=item.send_started_at or item.updated_at,
            )
            session.add(pub)

    return results
