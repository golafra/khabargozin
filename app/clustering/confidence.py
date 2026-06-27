"""Cluster confidence, stability, and publish eligibility."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clustering.lineage import independent_lineage_diversity, recalculate_independent_sources
from app.config import get_settings
from app.db.models.audit_log import AuditLog
from app.db.models.cluster import Cluster
from app.db.models.message import Message
from app.db.models.source import Source


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> int:
    return int(max(lo, min(hi, round(value))))


def compute_cluster_stability(session: Session, cluster_id: int) -> int:
    settings = get_settings()
    since = datetime.now(timezone.utc) - timedelta(hours=settings.CLUSTER_STABILITY_WINDOW_HOURS)
    merge_actions = (
        "merged_into_cluster",
        "reconcile_merge",
        "new_cluster",
    )
    split_actions = ("reconcile_split",)

    merge_count = session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.entity_type == "cluster",
            AuditLog.entity_id == cluster_id,
            AuditLog.action.in_(merge_actions),
            AuditLog.created_at >= since,
        )
    ) or 0
    split_count = session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.entity_type == "cluster",
            AuditLog.entity_id == cluster_id,
            AuditLog.action.in_(split_actions),
            AuditLog.created_at >= since,
        )
    ) or 0
    raw = 100 - (merge_count * 8 + split_count * 12)
    return _clamp(raw)


def message_velocity_score(session: Session, cluster_id: int, topic: str | None) -> float:
    since = datetime.now(timezone.utc) - timedelta(minutes=30)
    count = session.scalar(
        select(func.count())
        .select_from(Message)
        .where(Message.cluster_id == cluster_id, Message.published_at >= since)
    ) or 0
    baseline = 3.0
    if topic in ("earthquake", "war", "breaking"):
        baseline = 5.0
    return min(1.0, count / baseline)


def avg_source_credibility(session: Session, cluster_id: int) -> float:
    rows = session.execute(
        select(Source.credibility_weight)
        .join(Message, Message.source_id == Source.id)
        .where(Message.cluster_id == cluster_id)
        .distinct()
    ).all()
    if not rows:
        return 0.5
    weights = [r[0] for r in rows]
    return min(1.0, sum(weights) / len(weights) / 1.5)


def compute_cluster_confidence(
    session: Session,
    cluster: Cluster,
    *,
    avg_hybrid: float = 0.7,
    avg_rerank: float = 0.7,
    fingerprint_consensus: float = 0.8,
) -> int:
    settings = get_settings()
    stability = cluster.cluster_stability if cluster.cluster_stability is not None else compute_cluster_stability(
        session, cluster.id
    )
    diversity = independent_lineage_diversity(session, cluster.id)
    credibility = avg_source_credibility(session, cluster.id)
    velocity = message_velocity_score(session, cluster.id, cluster.topic)

    if cluster.story_phase == "breaking":
        stability_weight = settings.STABILITY_WEIGHT_BREAKING
    else:
        stability_weight = 0.15

    velocity_weight = 0.15 - stability_weight
    raw = (
        0.25 * avg_hybrid * 100
        + 0.20 * avg_rerank * 100
        + 0.15 * fingerprint_consensus * 100
        + 0.15 * diversity * 100
        + 0.10 * credibility * 100
        + stability_weight * stability
        + velocity_weight * velocity * 100
    )
    return _clamp(raw)


def update_cluster_confidence_metrics(session: Session, cluster_id: int, debug: dict | None = None) -> None:
    cluster = session.get(Cluster, cluster_id)
    if not cluster:
        return
    cluster.cluster_stability = compute_cluster_stability(session, cluster_id)
    cluster.independent_source_count = recalculate_independent_sources(session, cluster_id)
    avg_hybrid = (debug or {}).get("avg_hybrid", 0.7)
    avg_rerank = (debug or {}).get("avg_rerank", 0.7)
    cluster.cluster_confidence = compute_cluster_confidence(
        session,
        cluster,
        avg_hybrid=avg_hybrid,
        avg_rerank=avg_rerank,
    )
    if debug:
        cluster.cluster_debug = debug


def publish_eligible(
    cluster: Cluster,
    *,
    ai_confidence: float | None = None,
    velocity_high: bool = False,
) -> tuple[bool, str]:
    settings = get_settings()
    conf = cluster.cluster_confidence or 0
    stab = cluster.cluster_stability or 0

    if conf < 65:
        return False, "cluster_confidence_low"

    if cluster.story_phase == "breaking" and velocity_high and conf >= settings.BREAKING_PUBLISH_MIN_CONFIDENCE:
        return True, "breaking_fast_track"

    if cluster.story_phase == "breaking":
        if conf >= 75 and stab >= 30:
            return True, "breaking_standard"
        return False, "breaking_stability"

    if conf >= settings.CONFIDENCE_AUTO_PUBLISH_MIN and stab >= settings.STABILITY_AUTO_PUBLISH_MIN:
        return True, "standard"

    if stab < 40:
        return False, "cluster_stability_low"

    return False, "below_publish_gates"
