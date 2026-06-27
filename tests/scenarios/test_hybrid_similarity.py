"""Hybrid similarity weight tests."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.clustering.feature_store import MessageFeatures
from app.clustering.similarity import hybrid_similarity


def _msg(text: str, embedding: list[float]):
    m = MagicMock()
    m.text = text
    m.embedding = embedding
    m.published_at = datetime.now(timezone.utc)
    return m


def test_breaking_weights_favor_embedding():
    fa = MessageFeatures(news_type="breaking", topic="earthquake", fingerprint={"topic": "earthquake", "topic_confidence": 0.9})
    fb = MessageFeatures(news_type="breaking", topic="earthquake", fingerprint={"topic": "earthquake", "topic_confidence": 0.9})
    a = _msg("زلزله تبریز", [1.0] + [0.0] * 1023)
    b = _msg("زلزله شدید تبریز", [0.99] + [0.01] + [0.0] * 1022)
    score = hybrid_similarity(a, b, fa, fb, news_type="breaking")
    assert score.adjusted_score > 0.5


def test_economic_keywords_matter():
    fa = MessageFeatures(
        news_type="economic",
        topic="economic",
        keywords=["بورس", "شاخص"],
        fingerprint={"topic": "economic", "topic_confidence": 0.9},
    )
    fb = MessageFeatures(
        news_type="economic",
        topic="economic",
        keywords=["بورس", "شاخص", "رشد"],
        fingerprint={"topic": "economic", "topic_confidence": 0.9},
    )
    a = _msg("بورس امروز", [0.5] + [0.0] * 1023)
    b = _msg("شاخص بورس رشد کرد", [0.4] + [0.1] + [0.0] * 1022)
    score = hybrid_similarity(a, b, fa, fb, news_type="economic")
    assert score.components["keyword"] > 0
