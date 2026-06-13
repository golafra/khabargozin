"""Re-queue cluster for reprocessing."""

import argparse
import sys

from app.db.models.cluster import Cluster
from app.db.session import get_session


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", type=int, required=True)
    args = parser.parse_args()

    session = get_session()
    try:
        cluster = session.get(Cluster, args.id)
        if not cluster:
            print(f"Cluster {args.id} not found")
            return 1

        cluster.status = "ai_ready"
        cluster.last_ai_processed_at = None
        session.commit()
        print(f"Cluster {args.id} re-queued as ai_ready")

        from app.tasks.ai import process_cloud_ai
        process_cloud_ai.delay()
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
