"""Event fingerprint — soft penalty with topic confidence gate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.clustering.keywords import extract_keywords
from app.clustering.news_type import TopicClassification, classify_news
from app.clustering.ner import extract_entities_typed
from app.config import get_settings

LOCATION_ALIASES: dict[str, set[str]] = {
    "تبریز": {"تبریز", "آذربایجان شرقی", "شمال غرب"},
    "تهران": {"تهران", "پایتخت", "مرکز"},
    "اصفهان": {"اصفهان"},
}

INCOMPATIBLE_TOPICS: set[frozenset[str]] = {
    frozenset({"earthquake", "economic"}),
    frozenset({"war", "economic"}),
    frozenset({"election", "earthquake"}),
    frozenset({"legal", "earthquake"}),
}


@dataclass
class FingerprintResult:
    block: bool
    penalty: float
    reason: str = ""


def _normalize_location(loc: str) -> str:
    loc = loc.strip().lower()
    for canonical, aliases in LOCATION_ALIASES.items():
        if loc in aliases or loc == canonical:
            return canonical
    return loc


def build_event_fingerprint(text: str, published_at: datetime | None = None) -> dict[str, Any]:
    classification = classify_news(text)
    entities = extract_entities_typed(text)
    keywords = extract_keywords(text)
    date_str = published_at.date().isoformat() if published_at else None
    return {
        "persons": entities.get("PERSON", []),
        "locations": entities.get("LOCATION", []),
        "organizations": entities.get("ORGANIZATION", []),
        "date": date_str,
        "topic": classification.topic,
        "topic_confidence": classification.topic_confidence,
        "news_type": classification.news_type,
        "keywords": keywords[:10],
    }


def topics_are_incompatible(topic_a: str, topic_b: str) -> bool:
    if topic_a == topic_b:
        return False
    if topic_a == "general" or topic_b == "general":
        return False
    pair = frozenset({topic_a, topic_b})
    return pair in INCOMPATIBLE_TOPICS


def _location_overlap(locs_a: list[str], locs_b: list[str]) -> bool:
    if not locs_a or not locs_b:
        return True
    na = {_normalize_location(x) for x in locs_a}
    nb = {_normalize_location(x) for x in locs_b}
    return bool(na & nb)


def _list_overlap(a: list[str], b: list[str]) -> bool:
    if not a or not b:
        return True
    sa = {x.strip().lower() for x in a}
    sb = {x.strip().lower() for x in b}
    return bool(sa & sb)


def fingerprint_compatibility(fp_a: dict[str, Any], fp_b: dict[str, Any]) -> FingerprintResult:
    settings = get_settings()
    topic_a = fp_a.get("topic") or "general"
    topic_b = fp_b.get("topic") or "general"
    conf_a = float(fp_a.get("topic_confidence") or 0.5)
    conf_b = float(fp_b.get("topic_confidence") or 0.5)

    if topics_are_incompatible(topic_a, topic_b):
        if min(conf_a, conf_b) > settings.TOPIC_HARD_BLOCK_CONFIDENCE:
            return FingerprintResult(block=True, penalty=1.0, reason="topic_hard_block")
        return FingerprintResult(
            block=False,
            penalty=settings.TOPIC_SOFT_PENALTY_MISMATCH,
            reason="topic_soft_penalty",
        )

    penalty = 0.0
    if not _location_overlap(fp_a.get("locations") or [], fp_b.get("locations") or []):
        penalty = max(penalty, 0.15)
    if not _list_overlap(fp_a.get("persons") or [], fp_b.get("persons") or []):
        penalty = max(penalty, 0.10)
    if not _list_overlap(fp_a.get("organizations") or [], fp_b.get("organizations") or []):
        penalty = max(penalty, 0.08)

    return FingerprintResult(block=False, penalty=penalty, reason="soft")


def apply_fingerprint_penalty(hybrid_score: float, fp_result: FingerprintResult) -> float:
    if fp_result.block:
        return 0.0
    settings = get_settings()
    return hybrid_score * (1.0 - fp_result.penalty * settings.FINGERPRINT_PENALTY_WEIGHT)


def aggregate_cluster_fingerprint(fingerprints: list[dict[str, Any]]) -> dict[str, Any]:
    if not fingerprints:
        return {}
    persons: set[str] = set()
    locations: set[str] = set()
    orgs: set[str] = set()
    keywords: set[str] = set()
    topic = fingerprints[0].get("topic", "general")
    topic_confidence = float(fingerprints[0].get("topic_confidence") or 0.5)
    for fp in fingerprints:
        persons.update(fp.get("persons") or [])
        locations.update(fp.get("locations") or [])
        orgs.update(fp.get("organizations") or [])
        keywords.update(fp.get("keywords") or [])
        tc = float(fp.get("topic_confidence") or 0)
        if tc > topic_confidence:
            topic = fp.get("topic", topic)
            topic_confidence = tc
    return {
        "persons": sorted(persons),
        "locations": sorted(locations),
        "organizations": sorted(orgs),
        "keywords": sorted(keywords)[:20],
        "topic": topic,
        "topic_confidence": topic_confidence,
    }
