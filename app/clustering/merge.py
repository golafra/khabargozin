"""Merge open clusters only — MVP."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.clustering.embedder import embed_text
from app.clustering.event_signature import build_event_signature
from app.clustering.lineage import recalculate_independent_sources
from app.clustering.ner import ner_overlap
from app.clustering.vector_search import find_similar_clusters
from app.config import get_settings
from app.db.models.cluster import Cluster
from app.db.models.message import Message
from app.resilience.locking import cluster_lock


OPEN_STATUSES = ("pending", "scored", "ai_done")


def find_merge_target(
    session: Session,
    message: Message,
    query_embedding: list[float],
) -> int | None:
    settings = get_settings()
    candidates = find_similar_clusters(session, query_embedding, statuses=OPEN_STATUSES)
    text = message.text or ""

    for cluster_id, sim in candidates:
        cluster = session.get(Cluster, cluster_id)
        if not cluster or cluster.status not in OPEN_STATUSES:
            continue

        ner_boost = 0.0
        if text:
            sample_msg = session.query(Message).filter_by(cluster_id=cluster_id).first()
            if sample_msg and sample_msg.text:
                ner_boost = ner_overlap(text, sample_msg.text)

        if sim >= settings.MERGE_OPEN_SIM:
            return cluster_id
        if sim >= settings.MERGE_OPEN_SIM_NER and ner_boost >= settings.MERGE_NER_BOOST_THRESHOLD:
            return cluster_id
    return None


def attach_message_to_cluster(session: Session, message_id: int, cluster_id: int) -> None:
    with cluster_lock(session, cluster_id) as cluster:
        msg = session.get(Message, message_id)
        if not msg or msg.cluster_id:
            return
        msg.cluster_id = cluster_id
        if msg.published_at:
            if not cluster.window_start or msg.published_at < cluster.window_start:
                cluster.window_start = msg.published_at
            if not cluster.window_end or msg.published_at > cluster.window_end:
                cluster.window_end = msg.published_at
        cluster.independent_source_count = recalculate_independent_sources(session, cluster_id)
        cluster.updated_at = datetime.now(timezone.utc)


def create_cluster_for_message(session: Session, message: Message, embedding: list[float]) -> Cluster:
    cluster = Cluster(
        status="pending",
        centroid_embedding=embedding,
        event_signature=build_event_signature(message.text or ""),
        window_start=message.published_at,
        window_end=message.published_at,
        independent_source_count=1,
        distinct_sources=1,
    )
    session.add(cluster)
    session.flush()
    message.cluster_id = cluster.id
    cluster.independent_source_count = recalculate_independent_sources(session, cluster.id)
    return cluster
