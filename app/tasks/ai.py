"""AI processing tasks."""

from datetime import datetime, timezone

from sqlalchemy import select

from app.ai.client import AIClient, circuit_breaker_open
from app.ai.guardrails import check_guardrails
from app.audit import write_audit_log
from app.config import get_settings
from app.db.models.ai_result import AIResult
from app.db.models.cluster import Cluster
from app.db.models.message import Message
from app.db.models.source import Source
from app.publisher.hold import enqueue_hold, needs_ai_rerun, should_hold
from app.publisher.routing import apply_publish_routing
from app.publisher.tracks import is_in_hold_queue
from app.resilience.task_lock import acquire_redis_lock, release_redis_lock
from app.tasks.celery_app import celery_app


def _build_messages_block(session, cluster_id: int) -> str:
    rows = session.execute(
        select(Message, Source)
        .join(Source, Message.source_id == Source.id)
        .where(Message.cluster_id == cluster_id)
        .order_by(Message.published_at.asc())
    ).all()
    parts = []
    for msg, src in rows:
        parts.append(f"[{src.display_name}] {msg.text or ''}")
    return "\n---\n".join(parts)


@celery_app.task(name="app.tasks.ai.process_cloud_ai", acks_late=True)
def process_cloud_ai() -> dict:
    settings = get_settings()
    lock_key = "task:process_cloud_ai"
    if not acquire_redis_lock(lock_key, settings.TASK_LOCK_TTL_AI_SECONDS):
        return {"skipped": True}

    from app.db.session import get_session

    session = get_session()
    processed = 0
    try:
        if circuit_breaker_open(session):
            return {"skipped": True, "reason": "circuit_breaker"}

        clusters = session.scalars(
            select(Cluster).where(Cluster.status == "ai_ready").limit(20)
        ).all()

        client = AIClient(session)
        for cluster in clusters:
            if cluster.locked_for_hold or is_in_hold_queue(session, cluster.id):
                continue

            if cluster.last_ai_processed_at and not needs_ai_rerun(
                cluster, cluster.independent_source_count
            ):
                continue

            messages_block = _build_messages_block(session, cluster.id)
            try:
                result, pt, ct, cost = client.analyze_cluster(
                    messages_block,
                    cluster.independent_source_count,
                    cluster.cluster_score or 0.0,
                )
            except Exception as exc:
                write_audit_log(
                    session,
                    entity_type="cluster",
                    entity_id=cluster.id,
                    action="ai_failed",
                    actor="ai_task",
                    reason="ai_parse_failed",
                    metadata={"error": str(exc)[:200]},
                )
                cluster.status = "ai_failed"
                session.commit()
                continue

            ok, guard_reason = check_guardrails(result, cluster.independent_source_count)
            ai_row = AIResult(
                cluster_id=cluster.id,
                schema_version=settings.AI_SCHEMA_VERSION,
                prompt_version=settings.PROMPT_VERSION,
                status=result.status,
                editorial_priority=result.editorial_priority,
                confidence=result.confidence,
                headline=result.headline,
                summary=result.summary,
                why_it_matters=result.why_it_matters,
                conflicts=result.conflicts,
                sources_used=result.sources_used,
                rejection_reason=result.rejection_reason if not ok else result.rejection_reason,
                sensitivity=result.sensitivity,
                needs_human_review=result.needs_human_review,
                raw_response=result.model_dump(),
                prompt_tokens=pt,
                completion_tokens=ct,
                cost_estimate_usd=cost,
            )
            session.add(ai_row)

            cluster.last_ai_processed_at = datetime.now(timezone.utc)
            cluster.ai_independent_source_count_at_run = cluster.independent_source_count
            cluster.sensitivity = result.sensitivity

            if should_hold(
                result.editorial_priority,
                cluster.independent_source_count,
                result.confidence,
                bool(result.conflicts),
            ):
                enqueue_hold(session, cluster.id, cluster.independent_source_count)
                cluster.status = "hold"
            else:
                apply_publish_routing(session, cluster, result)

            session.commit()
            processed += 1

        return {"processed": processed}
    finally:
        session.close()
        release_redis_lock(lock_key)
