"""Dynamic threshold with cold-start strategy."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models.cluster import Cluster
from app.db.models.message import Message


def should_skip_clustering(session: Session) -> tuple[bool, str]:
    settings = get_settings()
    uptime = datetime.now(timezone.utc) - settings.APP_START_TIME
    if uptime < timedelta(minutes=settings.COLD_START_WARMUP_MINUTES):
        return True, "warmup"

    total_messages = session.scalar(select(func.count()).select_from(Message)) or 0
    if total_messages < settings.COLD_START_MIN_MESSAGES:
        return False, "bootstrap"
    return False, "steady"


def effective_threshold(session: Session) -> float:
    settings = get_settings()
    _, phase = should_skip_clustering(session)

    if phase in ("warmup", "bootstrap"):
        return settings.CLUSTER_SCORE_FALLBACK_THRESHOLD

    uptime = datetime.now(timezone.utc) - settings.APP_START_TIME
    if uptime < timedelta(hours=settings.COLD_START_DYNAMIC_AFTER_HOURS):
        return settings.CLUSTER_SCORE_FALLBACK_THRESHOLD

    active_count = session.scalar(
        select(func.count())
        .select_from(Cluster)
        .where(Cluster.status.in_(("scored", "ai_done", "published")))
        .where(Cluster.cluster_score.isnot(None))
    ) or 0

    if active_count < settings.MIN_CLUSTERS_FOR_PERCENTILE:
        return settings.CLUSTER_SCORE_FALLBACK_THRESHOLD

    scores = [
        float(s)
        for s in session.scalars(
            select(Cluster.cluster_score)
            .where(Cluster.cluster_score.isnot(None))
            .order_by(Cluster.last_scored_at.desc())
            .limit(200)
        ).all()
    ]
    if not scores:
        return settings.CLUSTER_SCORE_FALLBACK_THRESHOLD

    scores_sorted = sorted(scores)
    idx = int(len(scores_sorted) * settings.CLUSTER_PERCENTILE / 100.0)
    idx = min(idx, len(scores_sorted) - 1)
    percentile_val = scores_sorted[idx]

    return max(
        settings.MIN_AI_SCORE_THRESHOLD,
        min(percentile_val, settings.MAX_AI_SCORE_THRESHOLD),
    )
