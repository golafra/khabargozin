"""Hold confirmation and expiry — phase 2."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.publisher.hold import check_hold_confirmations, should_hold, needs_ai_rerun
from app.db.models.cluster import Cluster


def test_should_hold_single_source_high_priority():
    assert should_hold(5, 1, 0.80, False) is True


def test_should_not_hold_multi_source():
    assert should_hold(5, 2, 0.80, False) is False


def test_needs_ai_rerun_on_source_change():
    cluster = Cluster(ai_independent_source_count_at_run=1)
    assert needs_ai_rerun(cluster, 2) is True
    assert needs_ai_rerun(cluster, 1) is False
