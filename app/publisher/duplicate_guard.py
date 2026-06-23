"""Block publishing a cluster that duplicates a recent publication."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clustering.topic_overlap import should_block_duplicate_publish
from app.clustering.vector_search import find_recent_published_similar
from app.db.models.ai_result import AIResult
from app.db.models.cluster import Cluster
from app.db.models.message import Message


def find_publish_duplicate(
    session: Session,
    cluster: Cluster,
) -> tuple[int, float, str] | None:
    """Return (existing_cluster_id, similarity, reason) if publish should be blocked."""
    if not cluster.centroid_embedding:
        return None

    ai_row = session.scalar(
        select(AIResult)
        .where(AIResult.cluster_id == cluster.id)
        .order_by(AIResult.created_at.desc())
        .limit(1)
    )
    headline = ai_row.headline if ai_row else ""
    summary = ai_row.summary if ai_row else ""

    sample_msg = session.scalar(
        select(Message)
        .where(Message.cluster_id == cluster.id)
        .order_by(Message.published_at.asc())
        .limit(1)
    )
    source_text = sample_msg.text if sample_msg else ""
    cluster_text = " ".join(p for p in (headline, summary, source_text) if p).strip()
    if not cluster_text:
        return None

    candidates = find_recent_published_similar(
        session,
        list(cluster.centroid_embedding),
        limit=6,
    )

    for other_id, sim in candidates:
        if other_id == cluster.id:
            continue
        other_ai = session.scalar(
            select(AIResult)
            .where(AIResult.cluster_id == other_id)
            .order_by(AIResult.created_at.desc())
            .limit(1)
        )
        other_headline = other_ai.headline if other_ai else ""
        other_summary = other_ai.summary if other_ai else ""
        other_msg = session.scalar(
            select(Message)
            .where(Message.cluster_id == other_id)
            .order_by(Message.published_at.asc())
            .limit(1)
        )
        other_source = other_msg.text if other_msg else ""
        other_text = " ".join(
            p for p in (other_headline, other_summary, other_source) if p
        ).strip()

        if should_block_duplicate_publish(sim, cluster_text, other_text):
            reason = "vector_sim" if sim >= 0.65 else "topic_overlap"
            return other_id, sim, reason

    return None
