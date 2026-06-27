"""Re-embed all messages and rebuild cluster centroids."""

from __future__ import annotations

from sqlalchemy import select

from app.clustering.anchor_selector import update_cluster_anchor
from app.clustering.pipeline import extract_message_features
from app.db.models.cluster import Cluster
from app.db.models.message import Message
from app.db.session import get_session
from scripts._util import configure_stdout


def reembed_all(batch_size: int = 200) -> dict:
    configure_stdout()
    session = get_session()
    processed = 0
    try:
        offset = 0
        while True:
            messages = session.scalars(
                select(Message)
                .where(Message.is_deleted.is_(False), Message.has_text.is_(True))
                .order_by(Message.id.asc())
                .offset(offset)
                .limit(batch_size)
            ).all()
            if not messages:
                break
            for msg in messages:
                extract_message_features(session, msg)
                processed += 1
            session.commit()
            offset += batch_size

        clusters = session.scalars(select(Cluster)).all()
        for cluster in clusters:
            update_cluster_anchor(session, cluster)
        session.commit()
        return {"messages": processed, "clusters": len(clusters)}
    finally:
        session.close()


if __name__ == "__main__":
    print(reembed_all())
