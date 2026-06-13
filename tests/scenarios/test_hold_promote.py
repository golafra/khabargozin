"""Hold promote triggers ai_ready when sources changed."""

from unittest.mock import MagicMock

from app.db.models.cluster import Cluster
from app.db.models.hold_queue import HoldQueue
from app.publisher.hold import promote_hold_cluster, needs_ai_rerun


def test_promote_with_source_change_sets_ai_ready():
    session = MagicMock()
    cluster = Cluster(id=1, independent_source_count=2, ai_independent_source_count_at_run=1)
    hold = HoldQueue(cluster_id=1, confirmation_count=2, expires_at=MagicMock())

    promote_hold_cluster(session, cluster, hold)
    assert cluster.status == "ai_ready"
    assert cluster.locked_for_hold is False
    session.delete.assert_called_with(hold)


def test_no_rerun_same_sources():
    cluster = Cluster(ai_independent_source_count_at_run=2)
    assert needs_ai_rerun(cluster, 2) is False
