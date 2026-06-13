"""Inspect a source — fetch status and stale warning."""

import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.config import get_settings
from app.db.models.message import Message
from app.db.models.source import Source
from app.db.session import get_session


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.inspect_source <username>")
        return 1

    username = sys.argv[1].lstrip("@")
    settings = get_settings()
    session = get_session()
    try:
        source = session.scalar(select(Source).where(Source.username == username))
        if not source:
            print(f"Source @{username} not found. Run seed_sources first.")
            return 1

        msg_count = session.scalar(
            select(func.count()).select_from(Message).where(Message.source_id == source.id)
        )
        print(f"Source: {source.display_name} (@{source.username})")
        print(f"  active={source.is_active} type={source.source_type} "
              f"credibility={source.credibility_weight}")
        print(f"  last_message_id={source.last_message_id}")
        print(f"  last_fetch={source.last_successful_fetch_at}")
        print(f"  errors={source.fetch_error_count} last_error={source.last_error}")
        print(f"  messages_in_db={msg_count}")

        if source.last_successful_fetch_at:
            stale_cutoff = datetime.now(timezone.utc) - timedelta(
                minutes=settings.SOURCE_STALE_ALERT_MINUTES
            )
            if source.last_successful_fetch_at < stale_cutoff:
                print(f"\n⚠ WARNING: source stale (>{settings.SOURCE_STALE_ALERT_MINUTES}min)")
        else:
            print("\n⚠ WARNING: never successfully fetched")

        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
