"""Inspect a cluster — messages, score, AI, outbox."""

import argparse
import json
import sys

from sqlalchemy import select

from app.db.models.ai_result import AIResult
from app.db.models.cluster import Cluster
from app.db.models.message import Message
from app.db.models.publication_outbox import PublicationOutbox
from app.db.models.source import Source
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

        print(f"Cluster {cluster.id}: status={cluster.status} score={cluster.cluster_score}")
        print(f"  independent_sources={cluster.independent_source_count} "
              f"distinct={cluster.distinct_sources}")
        print(f"  sensitivity={cluster.sensitivity} locked_for_hold={cluster.locked_for_hold}")

        rows = session.execute(
            select(Message, Source)
            .join(Source, Message.source_id == Source.id)
            .where(Message.cluster_id == cluster.id)
            .order_by(Message.published_at.asc())
        ).all()
        print(f"\nMessages ({len(rows)}):")
        for msg, src in rows:
            preview = (msg.text or "")[:80].replace("\n", " ")
            print(f"  [{src.username}] id={msg.message_id} {preview}...")

        ai = session.scalars(
            select(AIResult).where(AIResult.cluster_id == cluster.id)
            .order_by(AIResult.created_at.desc()).limit(1)
        ).first()
        if ai:
            print(f"\nAI result: status={ai.status} priority={ai.editorial_priority} "
                  f"confidence={ai.confidence}")
            print(f"  headline: {ai.headline[:100]}")

        outbox = session.scalar(
            select(PublicationOutbox).where(PublicationOutbox.cluster_id == cluster.id)
        )
        if outbox:
            print(f"\nOutbox: track={outbox.track} status={outbox.status}")

        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
