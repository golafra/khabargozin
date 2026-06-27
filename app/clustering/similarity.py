"""Hybrid similarity — embedding + entity + keyword + time decay."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from app.clustering.embedder import embedding_to_list
from app.clustering.feature_store import MessageFeatures
from app.clustering.fingerprint import apply_fingerprint_penalty, fingerprint_compatibility
from app.clustering.news_type import merge_threshold_for_news_type
from app.config import get_settings
from app.db.models.message import Message

WEIGHTS: dict[str, tuple[float, float, float, float]] = {
    "breaking": (0.55, 0.25, 0.10, 0.10),
    "economic": (0.35, 0.20, 0.35, 0.10),
    "general": (0.45, 0.25, 0.20, 0.10),
}


@dataclass
class HybridScore:
    score: float
    adjusted_score: float
    should_merge: bool
    components: dict[str, float]
    fingerprint_block: bool = False
    match_reason: str = ""


def cosine_embedding(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b:
        return 0.0
    va = np.array(a, dtype=float)
    vb = np.array(b, dtype=float)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def jaccard(a: list[str] | set[str], b: list[str] | set[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def typed_entity_overlap(entities_a: dict[str, list[str]], entities_b: dict[str, list[str]]) -> float:
    weights = {"PERSON": 0.4, "ORGANIZATION": 0.35, "LOCATION": 0.25}
    total_w = 0.0
    total_score = 0.0
    for key, w in weights.items():
        ea = entities_a.get(key) or []
        eb = entities_b.get(key) or []
        if ea or eb:
            total_w += w
            total_score += w * jaccard(ea, eb)
    return total_score / total_w if total_w else 0.0


def time_decay(t_a: datetime | None, t_b: datetime | None, half_life_hours: float = 6.0) -> float:
    if not t_a or not t_b:
        return 0.5
    delta_h = abs((t_a - t_b).total_seconds()) / 3600.0
    return math.exp(-delta_h / half_life_hours)


def hybrid_similarity(
    msg_a: Message,
    msg_b: Message,
    features_a: MessageFeatures,
    features_b: MessageFeatures,
    *,
    news_type: str | None = None,
) -> HybridScore:
    nt = news_type or features_a.news_type or "general"
    w_emb, w_ent, w_kw, w_time = WEIGHTS.get(nt, WEIGHTS["general"])

    emb = cosine_embedding(embedding_to_list(msg_a.embedding), embedding_to_list(msg_b.embedding))
    ent = typed_entity_overlap(features_a.entities, features_b.entities)
    kw = jaccard(features_a.keywords, features_b.keywords)
    td = time_decay(msg_a.published_at, msg_b.published_at)

    score = w_emb * emb + w_ent * ent + w_kw * kw + w_time * td
    fp_a = features_a.fingerprint or {}
    fp_b = features_b.fingerprint or {}
    fp_result = fingerprint_compatibility(fp_a, fp_b)
    if fp_result.block:
        return HybridScore(
            score=score,
            adjusted_score=0.0,
            should_merge=False,
            components={"embedding": emb, "entity": ent, "keyword": kw, "time": td},
            fingerprint_block=True,
            match_reason=fp_result.reason,
        )

    adjusted = apply_fingerprint_penalty(score, fp_result)
    threshold = merge_threshold_for_news_type(nt)
    should = adjusted >= threshold
    reason = "hybrid"
    if fp_result.penalty > 0:
        reason = fp_result.reason

    return HybridScore(
        score=round(score, 4),
        adjusted_score=round(adjusted, 4),
        should_merge=should,
        components={"embedding": emb, "entity": ent, "keyword": kw, "time": td},
        match_reason=reason,
    )
