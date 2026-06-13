"""Batch adaptive interval."""

from unittest.mock import MagicMock, patch

from app.publisher.tracks import batch_interval_minutes
from app.config import Settings


def test_busy_queue_shorter_interval():
    settings = Settings(
        BATCH_QUEUE_BUSY_THRESHOLD=5,
        BATCH_PUBLISH_INTERVAL_MINUTES=15,
        BATCH_PUBLISH_INTERVAL_BUSY_MINUTES=5,
    )
    session = MagicMock()
    session.scalar.return_value = 10  # busy queue

    with patch("app.publisher.tracks.get_settings", return_value=settings):
        interval = batch_interval_minutes(session)
    assert interval == 5


def test_normal_queue_standard_interval():
    settings = Settings(
        BATCH_QUEUE_BUSY_THRESHOLD=5,
        BATCH_PUBLISH_INTERVAL_MINUTES=15,
        BATCH_PUBLISH_INTERVAL_BUSY_MINUTES=5,
    )
    session = MagicMock()
    session.scalar.return_value = 2

    with patch("app.publisher.tracks.get_settings", return_value=settings):
        interval = batch_interval_minutes(session)
    assert interval == 15
