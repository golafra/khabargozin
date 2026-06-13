"""Data archiving — phase 2."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings


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
