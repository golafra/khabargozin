"""Lightweight keyword extraction (RAKE-style)."""

from __future__ import annotations

import re
from collections import Counter

from app.clustering.text_normalize import normalize_for_clustering

_STOPWORDS = frozenset(
    {
        "که", "در", "به", "از", "با", "این", "آن", "را", "و", "برای", "تا",
        "امروز", "شد", "شده", "است", "بود", "های", "یک", "دو", "هر", "گفت",
        "می", "بر", "تا", "نیز", "هم", "برای",
    }
)

_TOKEN_RE = re.compile(r"[\w\u0600-\u06FF]{2,}")


def extract_keywords(text: str, top_n: int = 10) -> list[str]:
    clean = normalize_for_clustering(text).lower()
    tokens = [t for t in _TOKEN_RE.findall(clean) if t not in _STOPWORDS and len(t) > 2]
    if not tokens:
        return []

    bigrams: Counter[str] = Counter()
    for i in range(len(tokens) - 1):
        phrase = f"{tokens[i]} {tokens[i + 1]}"
        bigrams[phrase] += 1
    unigrams = Counter(tokens)

    scored: dict[str, float] = {}
    for phrase, count in bigrams.items():
        parts = phrase.split()
        denom = sum(unigrams[p] for p in parts) or 1
        scored[phrase] = count / denom
    for word, count in unigrams.items():
        scored[word] = max(scored.get(word, 0), count / len(tokens))

    ranked = sorted(scored.items(), key=lambda x: x[1], reverse=True)
    return [k for k, _ in ranked[:top_n]]
