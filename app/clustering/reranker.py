"""Cross-encoder reranker implementations."""

from __future__ import annotations

import os
from functools import lru_cache

from app.clustering.embedder import text_similarity
from app.clustering.ml_device import get_ml_device
from app.clustering.providers.reranker import CrossEncoderProvider
from app.clustering.topic_overlap import topic_overlap
from app.config import get_settings


class OfflineReranker(CrossEncoderProvider):
    """Fallback combining lexical + embedding similarity."""

    def score(self, text_a: str, text_b: str) -> float:
        emb = text_similarity(text_a, text_b)
        lex = topic_overlap(text_a, text_b)
        return 0.65 * emb + 0.35 * lex


class SentenceTransformersReranker(CrossEncoderProvider):
    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self._model_name, device=get_ml_device())
        return self._model

    def score(self, text_a: str, text_b: str) -> float:
        if not text_a.strip() or not text_b.strip():
            return 0.0
        model = self._load()
        raw = model.predict([(text_a, text_b)])
        return float(raw[0]) if hasattr(raw, "__len__") else float(raw)


@lru_cache(maxsize=1)
def get_reranker() -> CrossEncoderProvider:
    settings = get_settings()
    if settings.RERANKER_PROVIDER == "offline" or os.environ.get("CLUSTERING_OFFLINE") == "1":
        return OfflineReranker()
    return SentenceTransformersReranker(settings.RERANKER_MODEL)


def rerank_candidates(query_text: str, candidates: list[tuple[int, str]]) -> list[tuple[int, float]]:
    """Score (cluster_id, sample_text) pairs; return sorted by score desc."""
    reranker = get_reranker()
    scored = [(cid, reranker.score(query_text, text)) for cid, text in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
