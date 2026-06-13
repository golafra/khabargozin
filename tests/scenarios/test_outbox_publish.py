"""Outbox dry_run mode."""

from unittest.mock import MagicMock, patch

from app.config import Settings
from app.db.models.cluster import Cluster
from app.ai.schemas import AIClusterOutput


def test_dry_run_outbox_status():
    settings = Settings(PUBLISH_MODE="dry_run")
    session = MagicMock()
    session.scalar.return_value = None  # no existing outbox

    cluster = Cluster(id=1, status="ai_done")
    result = AIClusterOutput(
        status="publish",
        editorial_priority=3,
        confidence=0.7,
        headline="تیتر",
        summary="خلاصه",
        why_it_matters="",
        sensitivity="normal",
    )

    with patch("app.config.get_settings", return_value=settings):
        from app.publisher.outbox import enqueue_initial
        outbox = enqueue_initial(session, cluster, result, "<b>test</b>", "batch")

    assert outbox is not None
    assert outbox.status == "dry_run"
