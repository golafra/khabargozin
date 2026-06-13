"""Hold expiry with frozen time."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

freezegun = pytest.importorskip("freezegun")

from app.db.models.cluster import Cluster
from app.db.models.hold_queue import HoldQueue
from app.publisher.hold import check_hold_confirmations


@freezegun.freeze_time("2026-06-13 12:00:00")
def test_hold_expires_when_single_source_past_deadline():
    now = datetime.now(timezone.utc)
    cluster = Cluster(
        id=1,
        independent_source_count=1,
        status="hold",
        locked_for_hold=True,
    )
    hold = HoldQueue(
        id=10,
        cluster_id=1,
        confirmation_count=1,
        expires_at=now - timedelta(minutes=5),
    )

    session = MagicMock()
    session.scalars.return_value.all.return_value = [hold]
    session.get.side_effect = lambda model, pk: cluster if pk == 1 else hold

    with patch("app.publisher.hold.hold_lock") as mock_lock:
        mock_lock.return_value.__enter__ = lambda s: hold
        mock_lock.return_value.__exit__ = lambda s, *a: None
        with patch("app.publisher.hold.write_audit_log"):
            result = check_hold_confirmations(session)

    assert result["expired"] == 1
    assert result["promoted"] == 0
    assert cluster.status == "rejected"
    assert cluster.locked_for_hold is False
