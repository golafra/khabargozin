"""Lexical topic overlap — catches same story with different formatting."""

import re

from app.clustering.text_normalize import normalize_for_clustering
from app.config import get_settings

_TOKEN_RE = re.compile(r"[\w\u0600-\u06FF]{2,}")

_STOPWORDS = frozenset(
    {
        "که",
        "در",
        "به",
        "از",
        "با",
        "این",
        "آن",
        "را",
        "و",
        "برای",
        "تا",
        "امروز",
        "روز",
        "شد",
        "شده",
        "است",
        "بود",
        "های",
        "هایی",
        "یک",
        "دو",
        "هر",
    }
)


def topic_tokens(text: str) -> set[str]:
    clean = normalize_for_clustering(text).lower()
    return {t for t in _TOKEN_RE.findall(clean) if t not in _STOPWORDS and len(t) > 2}


def topic_overlap(text_a: str, text_b: str) -> float:
    tokens_a = topic_tokens(text_a)
    tokens_b = topic_tokens(text_b)
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def should_merge_open(
    sim: float,
    text_a: str,
    text_b: str,
    *,
    ner_boost: float = 0.0,
) -> bool:
    settings = get_settings()
    overlap = topic_overlap(text_a, text_b)

    if sim >= settings.MERGE_OPEN_SIM:
        return True
    if (
        overlap >= settings.MERGE_TOPIC_OVERLAP
        and sim >= settings.MERGE_OPEN_SIM_TOPIC
    ):
        return True
    if (
        sim >= settings.MERGE_OPEN_SIM_NER
        and ner_boost >= settings.MERGE_NER_BOOST_THRESHOLD
    ):
        return True
    return False


def should_merge_published(sim: float, text_a: str, text_b: str, *, ner_boost: float = 0.0) -> bool:
    settings = get_settings()
    overlap = topic_overlap(text_a, text_b)

    if sim >= settings.MERGE_PUBLISHED_SIM:
        return True
    if (
        overlap >= settings.MERGE_TOPIC_OVERLAP
        and sim >= settings.MERGE_PUBLISHED_SIM_TOPIC
    ):
        return True
    if ner_boost >= settings.MERGE_PUBLISHED_NER and sim >= settings.MERGE_PUBLISHED_SIM_HIGH:
        return True
    if overlap >= settings.MERGE_TOPIC_OVERLAP_STRONG and sim >= settings.MERGE_OPEN_SIM_TOPIC:
        return True
    return False


def should_block_duplicate_publish(sim: float, text_a: str, text_b: str) -> bool:
    settings = get_settings()
    overlap = topic_overlap(text_a, text_b)
    if sim >= settings.DUPLICATE_PUBLISH_SIM:
        return True
    return (
        overlap >= settings.MERGE_TOPIC_OVERLAP_STRONG
        and sim >= settings.DUPLICATE_PUBLISH_SIM_TOPIC
    )
