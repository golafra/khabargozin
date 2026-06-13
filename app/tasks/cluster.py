"""Clustering tasks."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import write_audit_log
from app.clustering.embedder import embed_text
from app.clustering.merge import (
    attach_message_to_cluster,
    create_cluster_for_message,
    find_merge_target,
)
from app.clustering.merge_published import find_published_merge_target
from app.clustering.scorer import score_cluster
from app.clustering.threshold import effective_threshold, should_skip_clustering
from app.config import get_settings
from app.db.models.cluster import Cluster
from app.db.models.message import Message
from app.publisher.retraction import detect_retraction_candidates, process_retraction_candidate
from app.publisher.supplemental import process_supplemental
from app.resilience.locking import mark_slow_op
from app.resilience.task_lock import acquire_redis_lock, release_redis_lock
from app.tasks.celery_app import celery_app


def _process_message(session: Session, message: Message) -> None:
    text = message.text or ""
    mark_slow_op(True)
    try:
        embedding = embed_text(text)
    finally:
        mark_slow_op(False)

    message.embedding = embedding
    target_id = find_merge_target(session, message, embedding)
    if target_id:
        attach_message_to_cluster(session, message.id, target_id)
        score_cluster(session, target_id)
        return

    published_target = find_published_merge_target(session, message, embedding)
    if published_target:
        attach_message_to_cluster(session, message.id, published_target)
        process_supplemental(session, published_target, text)
        for cid in detect_retraction_candidates(session, message):
            process_retraction_candidate(session, cid, message)
        return

    create_cluster_for_message(session, message, embedding)
    score_cluster(session, message.cluster_id)


@celery_app.task(name="app.tasks.cluster.cluster_pending_messages", acks_late=True)
def cluster_pending_messages() -> dict:
    settings = get_settings()
    lock_key = "task:cluster_pending_messages"
    if not acquire_redis_lock(lock_key, settings.TASK_LOCK_TTL_CLUSTER_SECONDS):
        return {"skipped": True}

    from app.db.session import get_session

    session = get_session()
    try:
        skip, phase = should_skip_clustering(session)
        if skip:
            return {"skipped": True, "phase": phase}

        threshold = effective_threshold(session)
        pending = session.scalars(
            select(Message).where(Message.cluster_id.is_(None)).order_by(Message.published_at.asc()).limit(100)
        ).all()

        processed = 0
        for msg in pending:
            _process_message(session, msg)
            session.commit()
            processed += 1

        scored = session.scalars(
            select(Cluster).where(Cluster.status == "scored", Cluster.cluster_score.isnot(None))
        ).all()
        for cluster in scored:
            if cluster.cluster_score and cluster.cluster_score >= threshold:
                cluster.status = "ai_ready"
                write_audit_log(
                    session,
                    entity_type="cluster",
                    entity_id=cluster.id,
                    action="threshold_passed",
                    actor="cluster_task",
                    old_status="scored",
                    new_status="ai_ready",
                )
            else:
                cluster.status = "below_threshold"
                cluster.status_reason = "below_threshold"
                write_audit_log(
                    session,
                    entity_type="cluster",
                    entity_id=cluster.id,
                    action="below_threshold",
                    actor="cluster_task",
                    reason="below_threshold",
                    old_status="scored",
                    new_status="below_threshold",
                )
        session.commit()
        return {"processed": processed, "phase": phase, "threshold": threshold}
    finally:
        session.close()
        release_redis_lock(lock_key)
