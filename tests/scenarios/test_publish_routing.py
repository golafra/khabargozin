"""Apply publish routing — reject and fast track."""

from unittest.mock import MagicMock, patch

from app.ai.schemas import AIClusterOutput
from app.db.models.cluster import Cluster
from app.publisher.routing import apply_publish_routing


def test_reject_sets_cluster_rejected():
    session = MagicMock()
    cluster = Cluster(id=1, independent_source_count=1, status="ai_ready")
    result = AIClusterOutput(
        status="reject",
        editorial_priority=3,
        confidence=0.3,
        headline="",
        summary="",
        rejection_reason="low quality",
    )
    with patch("app.publisher.routing.write_audit_log"):
        track = apply_publish_routing(session, cluster, result)
    assert track == "reject"
    assert cluster.status == "rejected"


def test_guardrail_fail_rejects_sensitive_single_source():
    session = MagicMock()
    cluster = Cluster(id=2, independent_source_count=1, status="ai_ready")
    result = AIClusterOutput(
        status="publish",
        editorial_priority=5,
        confidence=0.85,
        headline="خبر امنیتی",
        summary="جزئیات",
        sensitivity="security",
    )
    with patch("app.publisher.routing.write_audit_log"):
        track = apply_publish_routing(session, cluster, result)
    assert track == "rejected"
    assert cluster.status == "rejected"
