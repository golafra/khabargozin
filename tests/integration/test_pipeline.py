"""Pipeline integration — fetch upsert, merge, routing, outbox."""

from datetime import datetime, timedelta, timezone

import pytest

from tests.integration.conftest import requires_db

pytestmark = requires_db

EMBED_A = [1.0, 0.0, 0.0] + [0.0] * 1021
EMBED_B = [0.99, 0.01, 0.0] + [0.0] * 1021


def _make_source(db_session, username: str = "IntTestSource"):
    from app.db.models.source import Source

    existing = db_session.query(Source).filter_by(username=username).first()
    if existing:
        return existing
    source = Source(username=username, display_name="Integration Test")
    db_session.add(source)
    db_session.flush()
    return source


def test_message_upsert_and_edit(db_session):
    from app.fetcher.base import RawMessage
    from app.tasks.fetch import _upsert_message

    source = _make_source(db_session)
    now = datetime.now(timezone.utc)
    raw = RawMessage(
        message_id=900001,
        text="خبر اولیه",
        published_at=now,
        edit_date=None,
    )
    assert _upsert_message(db_session, source, raw) == "inserted"
    assert _upsert_message(db_session, source, raw) == "unchanged"

    edited = RawMessage(
        message_id=900001,
        text="خبر ویرایش‌شده",
        published_at=now,
        edit_date=now + timedelta(minutes=5),
    )
    assert _upsert_message(db_session, source, edited) == "updated"


def test_merge_two_messages_same_cluster(db_session):
    from app.clustering.merge import attach_message_to_cluster, create_cluster_for_message, find_merge_target
    from app.db.models.message import Message

    source_a = _make_source(db_session, "MergeA")
    source_b = _make_source(db_session, "MergeB")
    now = datetime.now(timezone.utc)

    msg_a = Message(
        source_id=source_a.id,
        message_id=900010,
        text="زلزله در فارس",
        published_at=now,
        has_text=True,
        embedding=EMBED_A,
    )
    db_session.add(msg_a)
    db_session.flush()

    cluster = create_cluster_for_message(db_session, msg_a, EMBED_A)
    cluster.status = "scored"
    db_session.flush()

    msg_b = Message(
        source_id=source_b.id,
        message_id=900011,
        text="زلزله در استان فارس گزارش شد",
        published_at=now + timedelta(minutes=2),
        has_text=True,
        embedding=EMBED_B,
    )
    db_session.add(msg_b)
    db_session.flush()

    target = find_merge_target(db_session, msg_b, EMBED_B)
    assert target == cluster.id
    attach_message_to_cluster(db_session, msg_b.id, cluster.id)
    db_session.flush()
    db_session.refresh(cluster)
    assert msg_b.cluster_id == cluster.id
    from app.clustering.lineage import distinct_source_count

    assert distinct_source_count(db_session, cluster.id) >= 2


def test_outbox_enqueue_idempotent(db_session):
    from app.ai.schemas import AIClusterOutput
    from app.db.models.cluster import Cluster
    from app.db.models.publication_outbox import PublicationOutbox
    from app.publisher.outbox import enqueue_initial

    cluster = Cluster(status="ai_done", independent_source_count=2)
    db_session.add(cluster)
    db_session.flush()

    result = AIClusterOutput(
        status="publish",
        editorial_priority=4,
        confidence=0.85,
        headline="تیتر تست",
        summary="خلاصه تست",
    )
    rendered = "<b>تیتر تست</b>\nخلاصه تست"
    first = enqueue_initial(db_session, cluster, result, rendered, "batch")
    second = enqueue_initial(db_session, cluster, result, rendered, "batch")
    db_session.flush()
    assert first is not None
    assert second.id == first.id
    count = db_session.query(PublicationOutbox).filter_by(cluster_id=cluster.id).count()
    assert count == 1
    assert first.status == "dry_run"


def test_apply_routing_rejects_sensitive_single_source(db_session):
    from app.ai.schemas import AIClusterOutput
    from app.db.models.cluster import Cluster
    from app.publisher.routing import apply_publish_routing

    cluster = Cluster(id=None, status="ai_ready", independent_source_count=1)
    db_session.add(cluster)
    db_session.flush()

    result = AIClusterOutput(
        status="publish",
        editorial_priority=5,
        confidence=0.9,
        headline="خبر امنیتی",
        summary="جزئیات",
        sensitivity="security",
    )
    track = apply_publish_routing(db_session, cluster, result)
    assert track == "rejected"
    assert cluster.status == "rejected"


def test_apply_routing_batch_track(db_session):
    from app.ai.schemas import AIClusterOutput
    from app.db.models.cluster import Cluster
    from app.db.models.publication_outbox import PublicationOutbox
    from app.publisher.routing import apply_publish_routing

    cluster = Cluster(status="ai_ready", independent_source_count=2)
    db_session.add(cluster)
    db_session.flush()

    result = AIClusterOutput(
        status="publish",
        editorial_priority=4,
        confidence=0.85,
        headline="خبر عادی",
        summary="خلاصه",
        sensitivity="normal",
    )
    track = apply_publish_routing(db_session, cluster, result)
    db_session.flush()
    assert track == "batch"
    assert cluster.status == "ai_done"
    outbox = db_session.query(PublicationOutbox).filter_by(cluster_id=cluster.id).one()
    assert outbox.track == "batch"
    assert outbox.status == "dry_run"
