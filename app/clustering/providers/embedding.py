"""Embedding provider abstraction."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...

    @property
    def dimension(self) -> int: ...
