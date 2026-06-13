"""Merge published strict — phase 2."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.clustering.merge_published import find_published_merge_target


def test_published_merge_requires_high_sim():
    session = MagicMock()
    message = MagicMock()
    message.text = "خبر جدید"
    message.published_at = datetime.now(timezone.utc)

    with patch("app.clustering.merge_published.find_similar_clusters", return_value=[(5, 0.90)]):
        with patch("app.clustering.merge_published.ner_overlap", return_value=0.6):
            cluster = MagicMock()
            cluster.status = "published"
            cluster.window_end = datetime.now(timezone.utc)
            cluster.event_signature = "abc"
            session.get.return_value = cluster
            sample = MagicMock(text="خبر جدید")
            session.query.return_value.filter_by.return_value.first.return_value = sample
            target = find_published_merge_target(session, message, [0.1] * 384)
    assert target == 5


def test_published_merge_rejects_low_sim():
    session = MagicMock()
    message = MagicMock()
    message.text = "متفاوت"
    message.published_at = datetime.now(timezone.utc)

    with patch("app.clustering.merge_published.find_similar_clusters", return_value=[(5, 0.70)]):
        cluster = MagicMock()
        cluster.status = "published"
        cluster.window_end = datetime.now(timezone.utc)
        session.get.return_value = cluster
        target = find_published_merge_target(session, message, [0.1] * 384)
    assert target is None
