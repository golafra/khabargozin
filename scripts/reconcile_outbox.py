"""Reconcile unknown outbox items."""

import argparse
import hashlib
import sys

from sqlalchemy import select

from app.db.models.publication import Publication
from app.db.models.publication_outbox import PublicationOutbox
from app.db.session import get_session


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    apply = args.apply

    session = get_session()
    try:
        unknowns = session.scalars(
            select(PublicationOutbox).where(PublicationOutbox.status == "unknown")
        ).all()

        if not unknowns:
            print("No unknown outbox items.")
            return 0

        print(f"Found {len(unknowns)} unknown items — manual review required.")
        print("See docs/outbox_reconcile.md for matching algorithm.\n")

        for item in unknowns:
            print(f"  outbox_id={item.id} cluster={item.cluster_id} "
                  f"preview={item.payload_preview[:60] if item.payload_preview else 'N/A'}...")
            if apply:
                print("    --apply: no automatic match — mark for manual review")
                item.status = "failed"
                item.error_message = "manual_reconcile_required"

        if apply:
            session.commit()
            print("\nMarked items for manual review.")
        else:
            print("\nDry run — use --apply to mark for review.")

        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
