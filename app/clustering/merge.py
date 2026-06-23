"""Merge open clusters only — MVP."""

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.clustering.embedder import embed_text
from app.clustering.event_signature import build_event_signature
from app.clustering.lineage import recalculate_independent_sources
from app.clustering.ner import ner_overlap
from app.clustering.topic_overlap import should_merge_open, topic_overlap
from app.clustering.vector_search import find_similar_clusters
from app.config import get_settings
from app.db.models.cluster import Cluster
from app.db.models.message import Message
from app.resilience.locking import cluster_lock


OPEN_STATUSES = ("pending", "scored", "ai_done")


def _safe_score(value: float | None) -> float | None:
    if value is None:
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return round(value, 3)


@dataclass
class MergeSearchResult:
    target_id: int | None = None
    best_similarity: float | None = None
    match_reason: str | None = None
    candidates: list[dict] = field(default_factory=list)


def search_merge_target(
    session: Session,
    message: Message,
    query_embedding: list[float],
) -> MergeSearchResult:
    settings = get_settings()
    candidates = find_similar_clusters(session, query_embedding, statuses=OPEN_STATUSES)
    text = message.text or ""
    result = MergeSearchResult()

    for cluster_id, sim in candidates:
        cluster = session.get(Cluster, cluster_id)
        if not cluster or cluster.status not in OPEN_STATUSES:
            continue

        sample_msg = session.query(Message).filter_by(cluster_id=cluster_id).first()
        sample_text = (sample_msg.text or "") if sample_msg else ""
        ner_boost = ner_overlap(text, sample_text) if text and sample_text else 0.0

        sample_src = ""
        if sample_msg:
            from app.db.models.source import Source

            src = session.get(Source, sample_msg.source_id)
            sample_src = src.username if src else ""

        result.candidates.append(
            {
                "cluster_id": cluster_id,
                "similarity": _safe_score(sim),
                "ner_boost": _safe_score(ner_boost),
                "topic_overlap": round(topic_overlap(text, sample_text), 3),
                "status": cluster.status,
                "score": cluster.cluster_score,
                "sources": cluster.independent_source_count,
                "preview": sample_text[:120],
                "sample_source": sample_src,
            }
        )

        if result.target_id is not None:
            continue

        if should_merge_open(sim, text, sample_text, ner_boost=ner_boost):
            result.target_id = cluster_id
            result.best_similarity = sim
            if sim >= settings.MERGE_OPEN_SIM:
                result.match_reason = "similarity"
            elif topic_overlap(text, sample_text) >= settings.MERGE_TOPIC_OVERLAP:
                result.match_reason = "similarity_topic"
            else:
                result.match_reason = "similarity_ner"

    return result


def find_merge_target(
    session: Session,
    message: Message,
    query_embedding: list[float],
) -> int | None:
    return search_merge_target(session, message, query_embedding).target_id


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
