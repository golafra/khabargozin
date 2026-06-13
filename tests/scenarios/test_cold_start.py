"""Cold start and percentile fallback."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.clustering.threshold import effective_threshold, should_skip_clustering
from app.config import Settings


def test_warmup_skips_clustering():
    settings = Settings(
        APP_START_TIME=datetime.now(timezone.utc),
        COLD_START_WARMUP_MINUTES=20,
    )
    with patch("app.clustering.threshold.get_settings", return_value=settings):
        session = MagicMock()
        skip, phase = should_skip_clustering(session)
    assert skip is True
    assert phase == "warmup"


def test_fallback_threshold_with_few_clusters():
    settings = Settings(
        APP_START_TIME=datetime.now(timezone.utc) - timedelta(hours=48),
        COLD_START_WARMUP_MINUTES=0,
        COLD_START_MIN_MESSAGES=0,
        COLD_START_DYNAMIC_AFTER_HOURS=0,
        MIN_CLUSTERS_FOR_PERCENTILE=20,
        CLUSTER_SCORE_FALLBACK_THRESHOLD=6.0,
    )
    session = MagicMock()
    session.scalar.return_value = 5  # few clusters

    with patch("app.clustering.threshold.get_settings", return_value=settings):
        with patch("app.clustering.threshold.should_skip_clustering", return_value=(False, "steady")):
            threshold = effective_threshold(session)
    assert threshold == 6.0
