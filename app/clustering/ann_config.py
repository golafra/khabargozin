"""Dynamic ANN top_k configuration."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models.cluster import Cluster

_OPEN_STATUSES = ("pending", "scored", "ai_done")


def ann_top_k(session: Session, news_type: str, topic: str | None = None) -> int:
    settings = get_settings()
    if news_type == "breaking" or topic in ("earthquake", "war", "accident"):
        return settings.ANN_TOP_K_BREAKING
    if news_type == "economic":
        base = settings.ANN_TOP_K_MIN
    else:
        base = settings.ANN_TOP_K_DEFAULT

    open_count = session.scalar(
        select(func.count()).select_from(Cluster).where(Cluster.status.in_(_OPEN_STATUSES))
    ) or 0
    if open_count > 50:
        return min(base + 5, settings.ANN_TOP_K_BREAKING)
    if open_count < 10:
        return max(settings.ANN_TOP_K_MIN, base - 2)
    return base
