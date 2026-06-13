"""Publish tasks."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.config import get_settings
from app.db.models.audit_log import AppState
from app.publisher.hold import check_hold_confirmations
from app.publisher.outbox import cleanup_stuck_outbox, process_outbox_item
from app.publisher.tracks import batch_interval_minutes
from app.resilience.task_lock import acquire_redis_lock, release_redis_lock
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.publish.publish_batch_queue", acks_late=False)
def publish_batch_queue() -> dict:
    settings = get_settings()
    lock_key = "task:publish_batch_queue"
    if not acquire_redis_lock(lock_key, settings.TASK_LOCK_TTL_PUBLISH_SECONDS):
        return {"skipped": True}

    from app.db.session import get_session
    from app.db.models.publication_outbox import PublicationOutbox

    session = get_session()
    published = 0
    try:
        cleanup_stuck_outbox(session)
        session.commit()

        interval = batch_interval_minutes(session)
        last_key = "last_batch_publish_at"
        last_row = session.get(AppState, last_key)
        now = datetime.now(timezone.utc)
        if last_row:
            last_at = datetime.fromisoformat(last_row.value)
            if last_at.tzinfo is None:
                last_at = last_at.replace(tzinfo=timezone.utc)
            if now - last_at < timedelta(minutes=interval):
                return {"skipped": True, "reason": "interval_not_elapsed", "interval": interval}

        pending = session.scalars(
            select(PublicationOutbox)
            .where(PublicationOutbox.track == "batch")
            .where(PublicationOutbox.status == "pending")
            .order_by(PublicationOutbox.created_at.asc())
            .limit(5)
        ).all()

        for item in pending:
            if process_outbox_item(session, item.id):
                published += 1
            session.commit()

        if published > 0:
            if last_row:
                last_row.value = now.isoformat()
            else:
                session.add(AppState(key=last_key, value=now.isoformat()))
            session.commit()

        return {"published": published, "interval_minutes": interval}
    finally:
        session.close()
        release_redis_lock(lock_key)


@celery_app.task(name="app.tasks.publish.check_hold_confirmations", acks_late=True)
def check_hold_confirmations_task() -> dict:
    from app.db.session import get_session

    session = get_session()
    try:
        count = check_hold_confirmations(session)
        session.commit()
        return {"processed": count}
    finally:
        session.close()


@celery_app.task(name="app.tasks.publish.publish_fast_item", acks_late=False)
def publish_fast_item(outbox_id: int) -> dict:
    from app.db.session import get_session

    session = get_session()
    try:
        ok = process_outbox_item(session, outbox_id)
        session.commit()
        return {"published": ok}
    finally:
        session.close()
