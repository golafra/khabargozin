"""Topic-based clustering and reconcile windows."""

from __future__ import annotations

TOPIC_ACTIVE_WINDOW_MINUTES: dict[str, int] = {
    "earthquake": 24 * 60,
    "accident": 24 * 60,
    "election": 14 * 24 * 60,
    "legal": 14 * 24 * 60,
    "war": 30 * 24 * 60,
    "conflict": 30 * 24 * 60,
    "economic": 7 * 24 * 60,
}

TOPIC_RECONCILE_LOOKBACK_HOURS: dict[str, int] = {
    "earthquake": 24,
    "accident": 24,
    "election": 14 * 24,
    "legal": 14 * 24,
    "war": 30 * 24,
    "conflict": 30 * 24,
    "economic": 7 * 24,
}


def active_window_minutes(topic: str | None) -> int:
    from app.config import get_settings

    if not topic:
        return get_settings().CLUSTER_ACTIVE_WINDOW_MINUTES
    return TOPIC_ACTIVE_WINDOW_MINUTES.get(topic, get_settings().CLUSTER_ACTIVE_WINDOW_MINUTES)


def reconcile_lookback_hours(topic: str | None) -> int:
    from app.config import get_settings

    if not topic:
        return get_settings().CLUSTER_LOOKBACK_HOURS
    return TOPIC_RECONCILE_LOOKBACK_HOURS.get(topic, get_settings().CLUSTER_LOOKBACK_HOURS)
