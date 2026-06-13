"""Retry all ai_failed clusters."""

import argparse

from sqlalchemy import select

from app.db.models.cluster import Cluster
from app.db.session import get_session
from scripts._util import configure_stdout


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    session = get_session()
    try:
        failed = session.scalars(
            select(Cluster).where(Cluster.status == "ai_failed")
        ).all()
        if not failed:
            print("No ai_failed clusters.")
            return 0

        ids = [c.id for c in failed]
        print(f"Found {len(ids)} ai_failed clusters: {ids}")
        if args.dry_run:
            return 0

        for cluster in failed:
            cluster.status = "ai_ready"
            cluster.last_ai_processed_at = None
            cluster.status_reason = None
        session.commit()
        print(f"Re-queued {len(ids)} clusters as ai_ready")

        from app.tasks.ai import process_cloud_ai
        process_cloud_ai.delay()
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
