"""E2E smoke test — fetch → cluster → AI → publish on test channel."""

import argparse
import time

from sqlalchemy import func, select

from app.config import get_settings
from app.db.models.cluster import Cluster
from app.db.models.message import Message
from app.db.models.publication import Publication
from app.db.models.publication_outbox import PublicationOutbox
from app.db.session import get_session
from scripts._util import configure_stdout


def _counts(session):
    return {
        "messages": session.scalar(select(func.count()).select_from(Message)) or 0,
        "pending_cluster": session.scalar(
            select(func.count()).select_from(Message).where(Message.cluster_id.is_(None))
        ) or 0,
        "ai_ready": session.scalar(
            select(func.count()).select_from(Cluster).where(Cluster.status == "ai_ready")
        ) or 0,
        "ai_failed": session.scalar(
            select(func.count()).select_from(Cluster).where(Cluster.status == "ai_failed")
        ) or 0,
        "outbox_pending": session.scalar(
            select(func.count()).select_from(PublicationOutbox).where(
                PublicationOutbox.status == "pending"
            )
        ) or 0,
        "published": session.scalar(select(func.count()).select_from(Publication)) or 0,
    }


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait", type=int, default=90, help="Seconds to wait between steps")
    parser.add_argument("--skip-fetch", action="store_true", help="Skip ICA fetch (faster)")
    args = parser.parse_args()

    settings = get_settings()
    if settings.PUBLISH_MODE == "production":
        print("ERROR: smoke test refuses production mode. Use test or dry_run.")
        return 1
    if settings.PUBLISH_MODE == "dry_run":
        print("WARNING: PUBLISH_MODE=dry_run — publish step will not send to Telegram")

    print(f"=== E2E Smoke Test (mode={settings.PUBLISH_MODE}) ===\n")
    session = get_session()
    before = _counts(session)
    session.close()
    print(f"Before: {before}")

    from app.tasks.fetch import fetch_all_sources
    from app.tasks.cluster import cluster_pending_messages
    from app.tasks.ai import process_cloud_ai
    from app.tasks.publish import publish_batch_queue

    steps = [
        ("fetch_all_sources", fetch_all_sources),
        ("cluster_pending_messages", cluster_pending_messages),
        ("process_cloud_ai", process_cloud_ai),
        ("publish_batch_queue", publish_batch_queue),
    ]
    if args.skip_fetch:
        steps = steps[1:]

    for name, fn in steps:
        print(f"\n--- Running {name} ---")
        try:
            result = fn()
            print(f"Result: {result}")
        except Exception as exc:
            print(f"FAILED {name}: {exc}")
            return 1
        time.sleep(min(args.wait, 30))

    session = get_session()
    after = _counts(session)
    session.close()
    print(f"\nAfter: {after}")

    ok = True
    if after["ai_failed"] > before["ai_failed"]:
        print(f"WARNING: ai_failed increased ({before['ai_failed']} → {after['ai_failed']})")
        ok = False
    if settings.PUBLISH_MODE != "dry_run":
        if after["published"] <= before["published"] and after["outbox_pending"] == before["outbox_pending"]:
            print("NOTE: no new publications (may be normal if no ai_ready clusters)")
    print("\nSmoke test completed." + (" OK" if ok else " WITH WARNINGS"))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
