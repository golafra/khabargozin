"""Fetch tasks."""

import hashlib
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.audit import write_audit_log
from app.config import get_settings
from app.db.models.message import Message
from app.db.models.source import Source
from app.fetcher.base import FetchCursor
from app.fetcher.factory import get_fetcher
from app.resilience.idempotency import content_hash
from app.resilience.redis_buffer import buffer_message, flush_buffer
from app.resilience.task_lock import acquire_redis_lock, release_redis_lock
from app.tasks.celery_app import app


def _overlap_start(source: Source, now: datetime) -> datetime:
    settings = get_settings()
    rolling_cutoff = now - timedelta(minutes=settings.FETCH_TIME_OVERLAP_MINUTES)
    last_fetch = source.last_successful_fetch_at or rolling_cutoff
    return min(rolling_cutoff, last_fetch)


def _insert_message(session: Session, source: Source, raw) -> bool:
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
        return False

    stmt = (
        insert(Message)
        .values(
            source_id=source.id,
            message_id=raw.message_id,
            reply_to_message_id=raw.reply_to_message_id,
            text=raw.text,
            text_hash=content_hash(raw.text or ""),
            url=raw.url,
            raw_payload=raw.raw_payload,
            media_meta=raw.media_meta,
            published_at=raw.published_at,
            edit_date=raw.edit_date,
            has_text=raw.has_text,
            message_type=raw.message_type,
        )
        .on_conflict_do_nothing(index_elements=["source_id", "message_id"])
    )
    result = session.execute(stmt)
    return result.rowcount > 0


def _fetch_source(session: Session, source: Source, fetcher) -> int:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    cursor = FetchCursor(
        last_message_id=source.last_message_id,
        overlap_start=_overlap_start(source, now),
    )
    messages = fetcher.fetch_messages(source, cursor)
    inserted = 0
    max_message_id = source.last_message_id or 0

    for raw in messages:
        if _insert_message(session, source, raw):
            inserted += 1
        if raw.message_id > max_message_id:
            max_message_id = raw.message_id

    if messages:
        source.last_message_id = max_message_id
        source.last_successful_fetch_at = now
        source.fetch_error_count = 0
        source.last_error = None
    session.commit()
    return inserted


@app.task(name="app.tasks.fetch.fetch_all_sources", acks_late=True)
def fetch_all_sources() -> dict:
    settings = get_settings()
    lock_key = "task:fetch_all_sources"
    if not acquire_redis_lock(lock_key, settings.TASK_LOCK_TTL_FETCH_SECONDS):
        return {"skipped": True, "reason": "task_already_running"}

    from app.db.session import get_session

    session = get_session()
    fetcher = get_fetcher()
    total_inserted = 0
    try:
        sources = session.scalars(select(Source).where(Source.is_active.is_(True))).all()
        for source in sources:
            try:
                total_inserted += _fetch_source(session, source, fetcher)
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
        return {"inserted": total_inserted}
    finally:
        session.close()
        release_redis_lock(lock_key)


@app.task(name="app.tasks.fetch.check_source_health", acks_late=True)
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
