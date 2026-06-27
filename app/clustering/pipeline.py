"""Message feature extraction pipeline."""

from __future__ import annotations

from datetime import datetime

from app.clustering.embedder import embed_text
from app.clustering.feature_store import FeatureStore, MessageFeatures
from app.clustering.fingerprint import build_event_fingerprint
from app.clustering.keywords import extract_keywords
from app.clustering.ner import extract_entities_typed
from app.clustering.news_type import classify_news
from app.clustering.text_normalize import normalize_for_clustering
from app.db.models.message import Message
from sqlalchemy.orm import Session


def extract_message_features(session: Session, message: Message) -> tuple[MessageFeatures, list[float]]:
    text = normalize_for_clustering(message.text or "") or (message.text or "")
    classification = classify_news(text)
    entities = extract_entities_typed(text)
    keywords = extract_keywords(text)
    fingerprint = build_event_fingerprint(text, message.published_at)

    features = MessageFeatures(
        entities=entities,
        keywords=keywords,
        fingerprint=fingerprint,
        news_type=classification.news_type,
        topic=classification.topic,
        topic_confidence=classification.topic_confidence,
        extractor_versions={"ner": "peyma-typed", "kw": "rake-1"},
    )
    embedding = embed_text(text)
    FeatureStore().write(session, message, features, embedding=embedding)
    return features, embedding
