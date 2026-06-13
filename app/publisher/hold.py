"""Hold queue management — phase 2."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import write_audit_log
from app.config import get_settings
from app.db.models.cluster import Cluster
from app.db.models.hold_queue import HoldQueue
from app.resilience.locking import hold_lock


def should_hold(
    editorial_priority: int,
    independent_source_count: int,
    confidence: float,
    has_conflicts: bool,
) -> bool:
    settings = get_settings()
    if editorial_priority < 4:
        return False
    return (
        independent_source_count < settings.HOLD_MIN_SOURCES
        or has_conflicts
        or confidence < settings.HOLD_CONFIDENCE_THRESHOLD
    )


def enqueue_hold(session: Session, cluster_id: int, independent_source_count: int) -> HoldQueue:
    settings = get_settings()
    existing = session.scalar(select(HoldQueue).where(HoldQueue.cluster_id == cluster_id))
    if existing:
        return existing

    cluster = session.get(Cluster, cluster_id)
    if cluster:
        cluster.locked_for_hold = True

    hold = HoldQueue(
        cluster_id=cluster_id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.HOLD_EXPIRE_MINUTES),
        confirmation_count=independent_source_count,
    )
    session.add(hold)
    return hold


def check_hold_confirmations(session: Session) -> int:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    holds = session.scalars(select(HoldQueue)).all()
    processed = 0

    for hold in holds:
        with hold_lock(session, hold.id):
            cluster = session.get(Cluster, hold.cluster_id)
            if not cluster:
                session.delete(hold)
                continue

            if cluster.independent_source_count >= settings.HOLD_MIN_SOURCES:
                cluster.locked_for_hold = False
                write_audit_log(
                    session,
                    entity_type="cluster",
                    entity_id=cluster.id,
                    action="hold_promoted",
                    actor="hold_task",
                    old_status="hold",
                    new_status="ready",
                )
                session.delete(hold)
                processed += 1
            elif hold.expires_at < now:
                cluster.status = "rejected"
                cluster.status_reason = "hold_expired"
                cluster.locked_for_hold = False
                write_audit_log(
                    session,
                    entity_type="cluster",
                    entity_id=cluster.id,
                    action="hold_expired",
                    actor="hold_task",
                    reason="hold_expired",
                    old_status="hold",
                    new_status="rejected",
                )
                session.delete(hold)
                processed += 1

    return processed


def needs_ai_rerun(cluster: Cluster, current_independent: int) -> bool:
    if cluster.ai_independent_source_count_at_run is None:
        return True
    return current_independent != cluster.ai_independent_source_count_at_run
