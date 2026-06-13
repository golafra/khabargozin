"""Data archiving — phase 2."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings


def archive_old_data(session: Session) -> dict[str, int]:
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.ARCHIVE_AFTER_DAYS)
    counts = {"messages": 0, "clusters": 0}

    msg_result = session.execute(
        text("""
            WITH moved AS (
                DELETE FROM messages
                WHERE published_at < :cutoff
                RETURNING id, source_id, message_id, text, published_at
            )
            INSERT INTO messages_archive (id, source_id, message_id, text, published_at)
            SELECT id, source_id, message_id, text, published_at FROM moved
        """),
        {"cutoff": cutoff},
    )
    counts["messages"] = msg_result.rowcount or 0

    cluster_result = session.execute(
        text("""
            WITH moved AS (
                DELETE FROM clusters c
                WHERE NOT EXISTS (SELECT 1 FROM messages m WHERE m.cluster_id = c.id)
                  AND c.created_at < :cutoff
                  AND c.status IN ('below_threshold', 'rejected', 'ai_failed')
                RETURNING id, cluster_score, status
            )
            INSERT INTO clusters_archive (id, cluster_score, status)
            SELECT id, cluster_score, status FROM moved
        """),
        {"cutoff": cutoff},
    )
    counts["clusters"] = cluster_result.rowcount or 0
    return counts
