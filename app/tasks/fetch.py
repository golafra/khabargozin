"""Fetch tasks."""

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.audit import write_audit_log
from app.config import get_settings
from app.db.models.message import Message
from app.db.models.source import Source
from app.fetcher.base import FetchCursor, RawMessage
from app.fetcher.factory import get_fetcher
from app.resilience.idempotency import content_hash
from app.resilience.redis_buffer import buffer_message, flush_buffer
from app.resilience.task_lock import acquire_redis_lock, release_redis_lock
from app.tasks.celery_app import celery_app


def _overlap_start(source: Source, now: datetime) -> datetime:
    settings = get_settings()
    rolling_cutoff = now - timedelta(minutes=settings.FETCH_TIME_OVERLAP_MINUTES)
    last_fetch = source.last_successful_fetch_at or rolling_cutoff
    return min(rolling_cutoff, last_fetch)


def _message_values(source: Source, raw: RawMessage) -> dict[str, Any]:
    return {
        "source_id": source.id,
        "message_id": raw.message_id,
        "reply_to_message_id": raw.reply_to_message_id,
        "text": raw.text,
        "text_hash": content_hash(raw.text or ""),
        "url": raw.url,
        "raw_payload": raw.raw_payload,
        "media_meta": raw.media_meta,
        "published_at": raw.published_at,
        "edit_date": raw.edit_date,
        "has_text": raw.has_text,
        "message_type": raw.message_type,
    }


def _upsert_message(session: Session, source: Source, raw: RawMessage) -> str:
    """Insert or update on edit_date change. Returns: inserted|updated|stale|unchanged."""
    settings = get_settings()
    lookback_cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.CLUSTER_LOOKBACK_HOURS)
    if raw.published_at < lookback_cutoff:
        write_audit_log(
            session,
            entity_type="message",
            entity_id=None,
            action="stale_rejected",
            actor="fetch_task",
            reason="stale_message",
            metadata={"message_id": raw.message_id, "source": source.username},
        )
        return "stale"

    existing = session.scalar(
        select(Message).where(
            Message.source_id == source.id,
            Message.message_id == raw.message_id,
        )
    )
    if existing:
        if raw.edit_date and (
            not existing.edit_date or raw.edit_date > existing.edit_date
        ):
            existing.text = raw.text
            existing.text_hash = content_hash(raw.text or "")
            existing.edit_date = raw.edit_date
            existing.url = raw.url
            existing.media_meta = raw.media_meta
            existing.raw_payload = raw.raw_payload
            existing.has_text = raw.has_text
            existing.message_type = raw.message_type
            write_audit_log(
                session,
                entity_type="message",
                entity_id=existing.id,
                action="message_edited",
                actor="fetch_task",
                metadata={"message_id": raw.message_id, "source": source.username},
            )
            return "updated"
        return "unchanged"

    stmt = (
        insert(Message)
        .values(**_message_values(source, raw))
        .on_conflict_do_nothing(index_elements=["source_id", "message_id"])
    )
    result = session.execute(stmt)
    return "inserted" if result.rowcount > 0 else "unchanged"


def _insert_from_buffer_payload(session: Session, payload: dict[str, Any]) -> None:
    source = session.get(Source, payload["source_id"])
    if not source:
        return
    raw = RawMessage(
        message_id=payload["message_id"],
        text=payload.get("text"),
        published_at=datetime.fromisoformat(payload["published_at"]),
        edit_date=(
            datetime.fromisoformat(payload["edit_date"])
            if payload.get("edit_date")
            else None
        ),
        reply_to_message_id=payload.get("reply_to_message_id"),
        url=payload.get("url"),
        media_meta=payload.get("media_meta"),
        raw_payload=payload.get("raw_payload") or {},
        has_text=payload.get("has_text", True),
        message_type=payload.get("message_type", "text"),
    )
    _upsert_message(session, source, raw)


def _flush_redis_buffer(session: Session) -> int:
    return flush_buffer(lambda p: _insert_from_buffer_payload(session, p))


def _buffer_raw_message(source: Source, raw: RawMessage) -> None:
    buffer_message({
        "source_id": source.id,
        "message_id": raw.message_id,
        "text": raw.text,
        "published_at": raw.published_at.isoformat(),
        "edit_date": raw.edit_date.isoformat() if raw.edit_date else None,
        "reply_to_message_id": raw.reply_to_message_id,
        "url": raw.url,
        "media_meta": raw.media_meta,
        "raw_payload": raw.raw_payload,
        "has_text": raw.has_text,
        "message_type": raw.message_type,
    })


def _recheck_recent_edits(session: Session, source: Source, fetcher) -> int:
    """Re-fetch recent message_ids to catch late edit_date changes."""
    settings = get_settings()
    fetch_one = getattr(fetcher, "fetch_message_by_id", None)
    if not fetch_one:
        return 0

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=settings.FETCH_EDIT_LOOKBACK_HOURS)
    message_ids = session.scalars(
        select(Message.message_id)
        .where(Message.source_id == source.id, Message.published_at >= cutoff)
        .order_by(Message.published_at.desc())
        .limit(settings.FETCH_EDIT_RECHECK_LIMIT)
    ).all()

    updated = 0
    for message_id in message_ids:
        try:
            raw = fetch_one(source, message_id)
            if not raw:
                continue
            outcome = _upsert_message(session, source, raw)
            if outcome == "updated":
                updated += 1
        except Exception:
            session.rollback()
        time.sleep(settings.ICA_FETCH_DELAY_SECONDS)
    return updated


def _fetch_source(session: Session, source: Source, fetcher) -> dict[str, int]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    cursor = FetchCursor(
        last_message_id=source.last_message_id,
        overlap_start=_overlap_start(source, now),
    )
    batch = fetcher.fetch_messages(source, cursor)
    stats = {"inserted": 0, "updated": 0, "edit_rechecked": 0}
    max_message_id = source.last_message_id or 0

    for raw in batch.messages:
        try:
            outcome = _upsert_message(session, source, raw)
            if outcome == "inserted":
                stats["inserted"] += 1
            elif outcome == "updated":
                stats["updated"] += 1
        except SQLAlchemyError:
            session.rollback()
            _buffer_raw_message(source, raw)
        if raw.message_id > max_message_id:
            max_message_id = raw.message_id

    if not batch.backfill_complete:
        write_audit_log(
            session,
            entity_type="source",
            entity_id=source.id,
            action="fetch_backfill_incomplete",
            actor="fetch_task",
            reason="fetch_backfill_incomplete",
            metadata={"username": source.username, "overlap_start": cursor.overlap_start.isoformat() if cursor.overlap_start else None},
        )

    if batch.messages:
        source.last_message_id = max_message_id
        source.last_successful_fetch_at = now
        source.fetch_error_count = 0
        source.last_error = None

    stats["edit_rechecked"] = _recheck_recent_edits(session, source, fetcher)
    session.commit()
    return stats


@celery_app.task(name="app.tasks.fetch.fetch_all_sources", acks_late=True)
def fetch_all_sources() -> dict:
    settings = get_settings()
    lock_key = "task:fetch_all_sources"
    if not acquire_redis_lock(lock_key, settings.TASK_LOCK_TTL_FETCH_SECONDS):
        return {"skipped": True, "reason": "task_already_running"}

    from app.db.session import get_session

    session = get_session()
    fetcher = get_fetcher()
    totals = {"inserted": 0, "updated": 0, "edit_rechecked": 0, "flushed_buffer": 0}
    try:
        try:
            totals["flushed_buffer"] = _flush_redis_buffer(session)
            session.commit()
        except SQLAlchemyError:
            session.rollback()

        sources = session.scalars(select(Source).where(Source.is_active.is_(True))).all()
        for source in sources:
            try:
                stats = _fetch_source(session, source, fetcher)
                totals["inserted"] += stats["inserted"]
                totals["updated"] += stats["updated"]
                totals["edit_rechecked"] += stats.get("edit_rechecked", 0)
            except Exception as exc:
                source.fetch_error_count += 1
                source.last_error = str(exc)[:500]
                session.commit()
                write_audit_log(
                    session,
                    entity_type="source",
                    entity_id=source.id,
                    action="fetch_failed",
                    actor="fetch_task",
                    metadata={"error": str(exc)[:200]},
                )
            time.sleep(settings.ICA_FETCH_DELAY_SECONDS)
        return totals
    finally:
        session.close()
        release_redis_lock(lock_key)


@celery_app.task(name="app.tasks.fetch.check_source_health", acks_late=True)
def check_source_health() -> dict:
    settings = get_settings()
    from app.db.session import get_session

    session = get_session()
    now = datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(minutes=settings.SOURCE_STALE_ALERT_MINUTES)
    stale_count = 0
    try:
        sources = session.scalars(select(Source).where(Source.is_active.is_(True))).all()
        for source in sources:
            if source.last_successful_fetch_at and source.last_successful_fetch_at < stale_cutoff:
                stale_count += 1
                write_audit_log(
                    session,
                    entity_type="source",
                    entity_id=source.id,
                    action="source_stale",
                    actor="health_task",
                    reason="source_stale",
                )
        session.commit()
        return {"stale_sources": stale_count}
    finally:
        session.close()
