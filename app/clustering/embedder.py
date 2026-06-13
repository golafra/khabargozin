"""Sentence-transformer embedder — loaded once per worker process."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

import numpy as np

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def embed_text(text: str) -> list[float]:
    if not text or not text.strip():
        dim = 384
        return [0.0] * dim
    model = _get_model()
    vector = model.encode(text, normalize_embeddings=False)
    return vector.tolist()


def text_similarity(text_a: str, text_b: str) -> float:
    va = np.array(embed_text(text_a))
    vb = np.array(embed_text(text_b))
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)
