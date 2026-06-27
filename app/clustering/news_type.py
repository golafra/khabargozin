"""News type and topic classification with confidence."""

from __future__ import annotations

import re
from dataclasses import dataclass

_BREAKING_KW = frozenset(
    {"فوری", "اضطراری", "هشدار", "زلزله", "انفجار", "ترور", "حمله", "شلیک", "آتش"}
)
_ECONOMIC_KW = frozenset(
    {"بورس", "نرخ", "دلار", "تومان", "سکه", "اقتصاد", "تورم", "بانک", "نفت", "بازار"}
)
_ELECTION_KW = frozenset({"انتخابات", "رای", "مجلس", "رئیس‌جمهور", "کاندید", "صندوق"})
_WAR_KW = frozenset({"جنگ", "درگیری", "نبرد", "موشک", "پهپاد", "ارتش", "جبهه"})
_LEGAL_KW = frozenset({"دادگاه", "قاضی", "محکوم", "پرونده", "دادستان", "حکم"})
_ACCIDENT_KW = frozenset({"تصادف", "سقوط", "آتش‌سوزی", "حادثه"})

_TOPIC_KEYWORDS: dict[str, frozenset[str]] = {
    "earthquake": frozenset({"زلزله", "لرزه", "ریشتر", "پس‌لرزه"}),
    "economic": _ECONOMIC_KW,
    "election": _ELECTION_KW,
    "war": _WAR_KW,
    "legal": _LEGAL_KW,
    "accident": _ACCIDENT_KW,
    "breaking": _BREAKING_KW,
}


@dataclass
class TopicClassification:
    news_type: str
    topic: str
    topic_confidence: float


def _score_keywords(text: str, keywords: frozenset[str]) -> tuple[int, list[str]]:
    lower = text.lower()
    hits = [kw for kw in keywords if kw in lower]
    return len(hits), hits


def classify_news(text: str) -> TopicClassification:
    if not text:
        return TopicClassification("general", "general", 0.3)

    scores: dict[str, int] = {}
    for topic, kws in _TOPIC_KEYWORDS.items():
        count, _ = _score_keywords(text, kws)
        if count:
            scores[topic] = count

    if not scores:
        return TopicClassification("general", "general", 0.4)

    best_topic = max(scores, key=scores.get)
    best_count = scores[best_topic]
    total_hits = sum(scores.values())
    confidence = min(0.95, 0.45 + 0.12 * best_count + 0.05 * (best_count / max(total_hits, 1)))

    # metaphor guard: economic + earthquake keyword → lower earthquake confidence
    if best_topic == "earthquake" and scores.get("economic", 0) > 0:
        econ_hits, _ = _score_keywords(text, _ECONOMIC_KW)
        if econ_hits >= best_count:
            return TopicClassification("economic", "economic", min(0.75, 0.4 + 0.1 * econ_hits))

    if best_topic in ("earthquake", "accident", "war") or best_count >= 2 and best_topic == "breaking":
        news_type = "breaking"
    elif best_topic == "economic":
        news_type = "economic"
    else:
        news_type = "general"

    return TopicClassification(news_type, best_topic, round(confidence, 3))


def merge_threshold_for_news_type(news_type: str) -> float:
    from app.config import get_settings

    s = get_settings()
    if news_type == "breaking":
        return s.MERGE_THRESHOLD_BREAKING
    if news_type == "economic":
        return s.MERGE_THRESHOLD_ECONOMIC
    return s.MERGE_THRESHOLD_GENERAL
