"""Merge open clusters — hybrid similarity + reranker."""

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clustering.anchor_selector import update_cluster_anchor
from app.clustering.ann_config import ann_top_k
from app.clustering.confidence import update_cluster_confidence_metrics
from app.clustering.embedder import embed_text
from app.clustering.event_signature import build_event_signature
from app.clustering.feature_store import FeatureStore, MessageFeatures
from app.clustering.fingerprint import aggregate_cluster_fingerprint
from app.clustering.lineage import recalculate_independent_sources
from app.clustering.reranker import rerank_candidates
from app.clustering.similarity import hybrid_similarity
from app.clustering.topic_windows import active_window_minutes
from app.clustering.vector_search import find_similar_clusters
from app.config import get_settings
from app.db.models.cluster import Cluster
from app.db.models.message import Message
from app.db.models.source import Source
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
    best_rerank: float | None = None
    match_reason: str | None = None
    candidates: list[dict] = field(default_factory=list)


def search_merge_target(
    session: Session,
    message: Message,
    query_embedding: list[float],
    features: MessageFeatures | None = None,
) -> MergeSearchResult:
    settings = get_settings()
    store = FeatureStore()
    if features is None:
        features = store.read(message)

    from datetime import timedelta

    window_cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=active_window_minutes(features.topic)
    )
    top_k = ann_top_k(session, features.news_type, features.topic)
    ann_candidates = find_similar_clusters(
        session,
        query_embedding,
        statuses=OPEN_STATUSES,
        limit=top_k,
        window_cutoff=window_cutoff,
    )

    result = MergeSearchResult()
    hybrid_ranked: list[tuple[int, float, str, dict]] = []

    for cluster_id, ann_sim in ann_candidates:
        cluster = session.get(Cluster, cluster_id)
        if not cluster or cluster.status not in OPEN_STATUSES:
            continue

        anchor = session.get(Message, cluster.anchor_message_id) if cluster.anchor_message_id else None
        if anchor is None:
            anchor = session.scalars(
                select(Message).where(Message.cluster_id == cluster_id).order_by(Message.published_at.asc()).limit(1)
            ).first()
        sample_text = (anchor.text or "") if anchor else ""
        sample_features = store.read(anchor) if anchor else MessageFeatures()

        if anchor and anchor.id != message.id:
            hybrid = hybrid_similarity(message, anchor, features, sample_features, news_type=features.news_type)
        else:
            continue

        result.candidates.append(
            {
                "cluster_id": cluster_id,
                "ann_similarity": _safe_score(ann_sim),
                "hybrid_score": _safe_score(hybrid.adjusted_score),
                "hybrid_raw": _safe_score(hybrid.score),
                "match_reason": hybrid.match_reason,
                "fingerprint_block": hybrid.fingerprint_block,
                "status": cluster.status,
                "sources": cluster.independent_source_count,
                "preview": sample_text[:120],
            }
        )

        if hybrid.fingerprint_block or not hybrid.should_merge:
            continue

        hybrid_ranked.append((cluster_id, hybrid.adjusted_score, hybrid.match_reason, hybrid.components))

    hybrid_ranked.sort(key=lambda x: x[1], reverse=True)
    top_for_rerank = hybrid_ranked[: settings.RERANK_TOP_K]

    if not top_for_rerank:
        return result

    rerank_inputs: list[tuple[int, str]] = []
    for cluster_id, _, _, _ in top_for_rerank:
        cluster = session.get(Cluster, cluster_id)
        anchor = session.get(Message, cluster.anchor_message_id) if cluster and cluster.anchor_message_id else None
        if anchor is None and cluster:
            anchor = session.scalars(
                select(Message).where(Message.cluster_id == cluster_id).order_by(Message.published_at.asc()).limit(1)
            ).first()
        rerank_inputs.append((cluster_id, (anchor.text or "") if anchor else ""))

    reranked = rerank_candidates(message.text or "", rerank_inputs)
    for cluster_id, rerank_score in reranked:
        if rerank_score >= settings.RERANK_MERGE_THRESHOLD:
            result.target_id = cluster_id
            result.best_rerank = rerank_score
            for cid, hybrid_score, reason, _ in top_for_rerank:
                if cid == cluster_id:
                    result.best_similarity = hybrid_score
                    result.match_reason = f"rerank:{reason}"
                    break
            break

    return result


def find_merge_target(
    session: Session,
    message: Message,
    query_embedding: list[float],
    features: MessageFeatures | None = None,
) -> int | None:
    return search_merge_target(session, message, query_embedding, features=features).target_id


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

        store = FeatureStore()
        fps = []
        for m in session.scalars(select(Message).where(Message.cluster_id == cluster_id)).all():
            feats = store.read(m)
            if feats.fingerprint:
                fps.append(feats.fingerprint)
        cluster.event_fingerprint = aggregate_cluster_fingerprint(fps)
        if cluster.event_fingerprint:
            cluster.topic = cluster.event_fingerprint.get("topic") or cluster.topic

        cluster.independent_source_count = recalculate_independent_sources(session, cluster_id)
        cluster.distinct_sources = len(
            {m.source_id for m in session.scalars(select(Message).where(Message.cluster_id == cluster_id)).all()}
        )
        cluster.updated_at = datetime.now(timezone.utc)

    update_cluster_anchor(session, session.get(Cluster, cluster_id))
    update_cluster_confidence_metrics(session, cluster_id)


def create_cluster_for_message(
    session: Session,
    message: Message,
    embedding: list[float],
    features: MessageFeatures | None = None,
) -> Cluster:
    store = FeatureStore()
    if features is None:
        features = store.read(message)

    fp = features.fingerprint or {}
    cluster = Cluster(
        status="pending",
        centroid_embedding=embedding,
        anchor_message_id=message.id,
        event_signature=build_event_signature(message.text or ""),
        event_fingerprint=fp,
        topic=features.topic,
        story_phase="breaking",
        window_start=message.published_at,
        window_end=message.published_at,
        independent_source_count=1,
        distinct_sources=1,
    )
    session.add(cluster)
    session.flush()
    message.cluster_id = cluster.id
    cluster.independent_source_count = recalculate_independent_sources(session, cluster.id)
    update_cluster_confidence_metrics(session, cluster.id)
    return cluster
