"""Feature store — read/write message features without schema churn."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.message import Message


@dataclass
class MessageFeatures:
    entities: dict[str, list[str]] = field(default_factory=dict)
    keywords: list[str] = field(default_factory=list)
    fingerprint: dict[str, Any] = field(default_factory=dict)
    news_type: str = "general"
    topic: str = "general"
    topic_confidence: float = 0.5
    extractor_versions: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entities": self.entities,
            "keywords": self.keywords,
            "fingerprint": self.fingerprint,
            "news_type": self.news_type,
            "topic": self.topic,
            "topic_confidence": self.topic_confidence,
            "extractor_versions": self.extractor_versions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> MessageFeatures:
        if not data:
            return cls()
        return cls(
            entities=data.get("entities") or {},
            keywords=data.get("keywords") or [],
            fingerprint=data.get("fingerprint") or {},
            news_type=data.get("news_type") or "general",
            topic=data.get("topic") or data.get("fingerprint", {}).get("topic") or "general",
            topic_confidence=float(data.get("topic_confidence", 0.5)),
            extractor_versions=data.get("extractor_versions") or {},
        )


class FeatureStore:
    def write(
        self,
        session: Session,
        message: Message,
        features: MessageFeatures,
        embedding: list[float] | None = None,
    ) -> None:
        message.features = features.to_dict()
        message.processed_at = datetime.now(timezone.utc)
        if embedding is not None:
            message.embedding = embedding

    def read(self, message: Message) -> MessageFeatures:
        return MessageFeatures.from_dict(message.features)

    def get_embedding(self, message: Message) -> list[float] | None:
        from app.clustering.embedder import embedding_to_list

        return embedding_to_list(message.embedding)

    def get_entities(self, message: Message) -> dict[str, list[str]]:
        return self.read(message).entities

    def get_keywords(self, message: Message) -> list[str]:
        return self.read(message).keywords
