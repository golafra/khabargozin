"""Sprint B.5 — AI dry run on real clusters."""

import argparse
import json
import sys

from sqlalchemy import select

from app.ai.client import AIClient, circuit_breaker_open
from app.db.models.cluster import Cluster
from app.db.models.message import Message
from app.db.models.source import Source
from app.db.session import get_session
from app.tasks.ai import _build_messages_block


def main() -> int:
    parser = argparse.ArgumentParser(description="AI dry run on real clusters")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()

    session = get_session()
    try:
        if circuit_breaker_open(session):
            print("Circuit breaker open — budget exceeded", file=sys.stderr)
            return 1

        clusters = session.scalars(
            select(Cluster)
            .where(Cluster.status.in_(("scored", "ai_ready", "ai_done")))
            .order_by(Cluster.cluster_score.desc().nullslast())
            .limit(args.limit)
        ).all()

        if not clusters:
            print("No clusters found. Run fetch + cluster first.")
            return 0

        client = AIClient(session)
        for cluster in clusters:
            block = _build_messages_block(session, cluster.id)
            print(f"\n{'='*60}\nCluster {cluster.id} score={cluster.cluster_score} "
                  f"sources={cluster.independent_source_count}")
            try:
                result, pt, ct, cost = client.analyze_cluster(
                    block,
                    cluster.independent_source_count,
                    cluster.cluster_score or 0.0,
                )
                print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
                print(f"tokens: {pt}+{ct} cost≈${cost:.4f}")
                print(f"headline len={len(result.headline)} summary len={len(result.summary)}")
            except Exception as exc:
                print(f"FAILED: {exc}", file=sys.stderr)
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
