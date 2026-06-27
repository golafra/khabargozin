"""Feature store read/write."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.clustering.feature_store import FeatureStore, MessageFeatures


def test_feature_store_roundtrip():
    session = MagicMock()
    msg = MagicMock()
    msg.id = 1
    features = MessageFeatures(
        entities={"PERSON": ["علی"], "LOCATION": [], "ORGANIZATION": []},
        keywords=["زلزله"],
        topic="earthquake",
    )
    store = FeatureStore()
    store.write(session, msg, features, embedding=[0.1] * 1024)
    assert msg.features["topic"] == "earthquake"
    assert msg.processed_at is not None
    read_back = store.read(msg)
    assert read_back.keywords == ["زلزله"]
