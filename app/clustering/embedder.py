"""Sentence-transformer embedder — loaded once per worker process."""

from __future__ import annotations

import hashlib
import os
from functools import lru_cache
from typing import Optional

import numpy as np

from app.clustering.ml_device import get_ml_device
from app.clustering.providers.embedding import EmbeddingProvider
from app.config import get_settings


def _offline_embedding(text: str, dim: int) -> list[float]:
    """Deterministic pseudo-embedding for tests without loading models."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values = [((digest[i % len(digest)] / 255.0) * 2 - 1) for i in range(dim)]
    norm = np.linalg.norm(values)
    if norm == 0:
        return [0.0] * dim
    return [float(v / norm) for v in values]


class SentenceTransformersEmbedding(EmbeddingProvider):
    def __init__(self, model_name: str, dimension: int) -> None:
        self._model_name = model_name
        self._dimension = dimension
        self._model = None

    @property
    def dimension(self) -> int:
        return self._dimension

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name, device=get_ml_device())
        return self._model

    def embed(self, text: str) -> list[float]:
        if not text or not text.strip():
            return [0.0] * self._dimension
        model = self._load()
        vector = model.encode(text, normalize_embeddings=True)
        return vector.tolist()


@lru_cache(maxsize=1)
def _get_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.CLUSTERING_OFFLINE or os.environ.get("CLUSTERING_OFFLINE") == "1":
        return _OfflineEmbedding(settings.EMBEDDING_DIM)
    return SentenceTransformersEmbedding(settings.EMBEDDING_MODEL, settings.EMBEDDING_DIM)


class _OfflineEmbedding(EmbeddingProvider):
    def __init__(self, dimension: int) -> None:
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str) -> list[float]:
        if not text or not text.strip():
            return [0.0] * self._dimension
        return _offline_embedding(text, self._dimension)


def _get_model():
    """Backward compat for celery preload."""
    provider = _get_provider()
    if isinstance(provider, SentenceTransformersEmbedding):
        return provider._load()
    return None


def embedding_to_list(embedding) -> list[float] | None:
    if embedding is None:
        return None
    if hasattr(embedding, "tolist"):
        return embedding.tolist()
    return list(embedding)


def embed_text(text: str) -> list[float]:
    return _get_provider().embed(text)


def text_similarity(text_a: str, text_b: str) -> float:
    va = np.array(embed_text(text_a))
    vb = np.array(embed_text(text_b))
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)
