"""Retry failed outbox publications."""

import sys

from sqlalchemy import select, update

from app.config import get_settings
from app.db.models.publication import Publication
from app.db.models.publication_outbox import PublicationOutbox
from app.db.session import get_session
from app.publisher.outbox import process_outbox_item
from scripts._util import configure_stdout


def main() -> int:
    configure_stdout()
    get_settings.cache_clear()
    settings = get_settings()
    print(f"publish_mode={settings.PUBLISH_MODE}")

    session = get_session()
    try:
        session.execute(
            update(PublicationOutbox)
            .where(PublicationOutbox.status.in_(("failed", "dry_run")))
            .values(status="pending", error_message=None)
        )
        session.commit()

        pending = session.scalars(
            select(PublicationOutbox)
            .where(PublicationOutbox.status == "pending")
            .order_by(PublicationOutbox.created_at.asc())
        ).all()

        if not pending:
            print("No pending outbox items.")
            return 0

        published = 0
        for item in pending:
            ok = process_outbox_item(session, item.id)
            session.commit()
            status = session.get(PublicationOutbox, item.id)
            print(f"cluster {item.cluster_id}: ok={ok} status={status.status if status else '?'}")
            if status and status.error_message:
                print(f"  error: {status.error_message}")
            if ok:
                published += 1

        pubs = session.scalars(select(Publication)).all()
        print(f"\nPublished {published}/{len(pending)}. Total publications: {len(pubs)}")
        return 0 if published > 0 else 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
