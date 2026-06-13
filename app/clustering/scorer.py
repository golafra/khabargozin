"""Cluster score calculation."""

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models.cluster import Cluster
from app.db.models.message import Message
from app.db.models.source import Source

URGENCY_KEYWORDS = [
    "فوری",
    "اضطراری",
    "هشدار",
    "زلزله",
    "انفجار",
    "تصمیم",
    "قطعی",
    "بورس",
    "نرخ",
]


def compute_cluster_score(
    session: Session,
    cluster: Cluster,
    independent_source_count: int,
) -> float:
    settings = get_settings()

    rows = session.execute(
        select(Message, Source)
        .join(Source, Message.source_id == Source.id)
        .where(Message.cluster_id == cluster.id)
    ).all()

    cap = settings.SCORER_SOURCE_CAP
    source_score = min(independent_source_count, cap) / cap

    source_weights: dict[int, float] = {}
    for msg, src in rows:
        source_weights[src.id] = src.credibility_weight
    if source_weights:
        credibility_score = sum(source_weights.values()) / len(source_weights) / 1.5
        credibility_score = min(credibility_score, 1.0)
    else:
        credibility_score = 0.0

    timestamps = [m.published_at for m, _ in rows if m.published_at]
    if len(timestamps) >= 2:
        span_minutes = (max(timestamps) - min(timestamps)).total_seconds() / 60.0
        speed_score = max(0.0, 1.0 - span_minutes / settings.SCORER_SPEED_CAP_MINUTES)
    else:
        speed_score = 1.0

    combined_text = " ".join((m.text or "") for m, _ in rows)
    keyword_hits = sum(1 for kw in URGENCY_KEYWORDS if kw in combined_text)
    urgency_score = min(keyword_hits, settings.SCORER_URGENCY_KEYWORD_CAP) / settings.SCORER_URGENCY_KEYWORD_CAP

    weights = {
        "sources": settings.SCORER_WEIGHT_SOURCES,
        "credibility": settings.SCORER_WEIGHT_CREDIBILITY,
        "speed": settings.SCORER_WEIGHT_SPEED,
        "urgency": settings.SCORER_WEIGHT_URGENCY,
        "topic": settings.SCORER_WEIGHT_TOPIC,
    }
    weighted_sum = (
        weights["sources"] * source_score
        + weights["credibility"] * credibility_score
        + weights["speed"] * speed_score
        + weights["urgency"] * urgency_score
    )
    active_weight = sum(weights.values())
    if active_weight == 0:
        return 1.0
    raw = 1 + 9 * (weighted_sum / active_weight)
    return max(1.0, min(10.0, raw))


def score_cluster(session: Session, cluster_id: int) -> float:
    from app.clustering.lineage import recalculate_independent_sources

    cluster = session.get(Cluster, cluster_id)
    if not cluster:
        return 0.0
    independent = recalculate_independent_sources(session, cluster_id)
    cluster.independent_source_count = independent
    cluster.distinct_sources = len(
        session.execute(
            select(Source.id)
            .join(Message, Message.source_id == Source.id)
            .where(Message.cluster_id == cluster_id)
            .distinct()
        ).scalars().all()
    )
    score = compute_cluster_score(session, cluster, independent)
    cluster.cluster_score = score
    cluster.last_scored_at = datetime.now(timezone.utc)
    cluster.status = "scored"
    return score
