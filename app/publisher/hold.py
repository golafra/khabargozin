"""Hold queue management — phase 2."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import write_audit_log
from app.config import get_settings
from app.db.models.ai_result import AIResult
from app.db.models.cluster import Cluster
from app.db.models.hold_queue import HoldQueue
from app.ai.schemas import AIClusterOutput
from app.publisher.routing import apply_publish_routing
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
        existing.confirmation_count = independent_source_count
        return existing

    cluster = session.get(Cluster, cluster_id)
    if cluster:
        cluster.locked_for_hold = True
        cluster.status = "hold"

    hold = HoldQueue(
        cluster_id=cluster_id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.HOLD_EXPIRE_MINUTES),
        confirmation_count=independent_source_count,
    )
    session.add(hold)
    return hold


def update_hold_confirmation(session: Session, cluster_id: int) -> None:
    """Called when clustering merges a new message into a held cluster."""
    hold = session.scalar(select(HoldQueue).where(HoldQueue.cluster_id == cluster_id))
    if not hold:
        return
    cluster = session.get(Cluster, cluster_id)
    if cluster:
        hold.confirmation_count = cluster.independent_source_count


def needs_ai_rerun(cluster: Cluster, current_independent: int) -> bool:
    if cluster.ai_independent_source_count_at_run is None:
        return True
    return current_independent != cluster.ai_independent_source_count_at_run


def route_promoted_hold(session: Session, cluster: Cluster) -> None:
    """Re-route to publish using latest AI result when sources unchanged."""
    ai_row = session.scalars(
        select(AIResult)
        .where(AIResult.cluster_id == cluster.id)
        .order_by(AIResult.created_at.desc())
        .limit(1)
    ).first()
    if not ai_row:
        cluster.status = "ai_ready"
        return

    result = AIClusterOutput(
        status=ai_row.status,
        editorial_priority=ai_row.editorial_priority,
        confidence=ai_row.confidence,
        headline=ai_row.headline,
        summary=ai_row.summary,
        why_it_matters=ai_row.why_it_matters,
        conflicts=ai_row.conflicts or [],
        sources_used=ai_row.sources_used or [],
        rejection_reason=ai_row.rejection_reason,
        sensitivity=ai_row.sensitivity,
        needs_human_review=ai_row.needs_human_review,
    )
    apply_publish_routing(session, cluster, result)


def promote_hold_cluster(session: Session, cluster: Cluster, hold: HoldQueue) -> None:
    cluster.locked_for_hold = False
    if needs_ai_rerun(cluster, cluster.independent_source_count):
        cluster.status = "ai_ready"
        cluster.last_ai_processed_at = None
        write_audit_log(
            session,
            entity_type="cluster",
            entity_id=cluster.id,
            action="hold_promoted",
            actor="hold_task",
            old_status="hold",
            new_status="ai_ready",
            metadata={"reason": "ai_rerun_required"},
        )
    else:
        route_promoted_hold(session, cluster)
        write_audit_log(
            session,
            entity_type="cluster",
            entity_id=cluster.id,
            action="hold_promoted",
            actor="hold_task",
            old_status="hold",
            new_status="ai_done",
            metadata={"reason": "existing_ai_result"},
        )
    session.delete(hold)


def check_hold_confirmations(session: Session) -> dict[str, int]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    holds = session.scalars(select(HoldQueue)).all()
    promoted = 0
    expired = 0

    for hold in holds:
        with hold_lock(session, hold.id):
            cluster = session.get(Cluster, hold.cluster_id)
            if not cluster:
                session.delete(hold)
                continue

            if cluster.independent_source_count >= settings.HOLD_MIN_SOURCES:
                promote_hold_cluster(session, cluster, hold)
                promoted += 1
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
                expired += 1

    return {"promoted": promoted, "expired": expired}
