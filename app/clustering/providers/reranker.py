"""Cross-encoder reranker provider abstraction."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CrossEncoderProvider(Protocol):
    def score(self, text_a: str, text_b: str) -> float: ...
