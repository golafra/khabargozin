"""Data archiving — phase 2."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.tasks.celery_app import celery_app


def archive_old_data(session: Session) -> dict[str, int]:
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.ARCHIVE_AFTER_DAYS)
    counts = {"messages": 0, "clusters": 0}

    try:
        result = session.execute(
            text("""
                WITH moved AS (
                    DELETE FROM messages
                    WHERE published_at < :cutoff
                    RETURNING *
                )
                INSERT INTO messages_archive SELECT * FROM moved
            """),
            {"cutoff": cutoff},
        )
        counts["messages"] = result.rowcount or 0
    except Exception:
        pass

    return counts


@celery_app.task(name="app.tasks.archive.archive_old_records", acks_late=True)
def archive_old_records() -> dict:
    from app.db.session import get_session

    session = get_session()
    try:
        counts = archive_old_data(session)
        session.commit()
        return counts
    finally:
        session.close()
