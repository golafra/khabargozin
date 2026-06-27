"""Cluster stability and publish eligibility."""

from unittest.mock import MagicMock, patch

from app.clustering.confidence import compute_cluster_stability, publish_eligible
from app.db.models.cluster import Cluster


def test_stability_drops_with_many_merges():
    session = MagicMock()
    session.scalar.side_effect = [8, 5]
    stability = compute_cluster_stability(session, 1)
    assert stability == 0


def test_breaking_fast_track_bypasses_stability():
    cluster = Cluster(story_phase="breaking", cluster_confidence=82, cluster_stability=10)
    ok, reason = publish_eligible(cluster, velocity_high=True)
    assert ok is True
    assert reason == "breaking_fast_track"


def test_low_confidence_blocks():
    cluster = Cluster(story_phase="confirmed", cluster_confidence=60, cluster_stability=80)
    ok, reason = publish_eligible(cluster)
    assert ok is False
    assert reason == "cluster_confidence_low"
