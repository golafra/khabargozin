"""Publication outbox pattern."""

import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import write_audit_log
from app.config import get_settings
from app.db.models.cluster import Cluster
from app.db.models.publication import Publication
from app.db.models.publication_outbox import PublicationOutbox
from app.publisher.bot import get_cached_chat_id, resolve_and_cache_chat, send_message_html
from app.publisher.formatter import format_publication_html
from app.publisher.tracks import route_track
from app.resilience.locking import outbox_lock


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def enqueue_initial(
    session: Session,
    cluster: Cluster,
    ai_result,
    rendered_html: str,
    track: str,
) -> PublicationOutbox | None:
    settings = get_settings()
    existing = session.scalar(
        select(PublicationOutbox).where(
            PublicationOutbox.cluster_id == cluster.id,
            PublicationOutbox.operation_type == "initial",
        )
    )
    if existing:
        return existing

    status = "dry_run" if settings.PUBLISH_MODE == "dry_run" else "pending"
    if track == "reject":
        return None

    outbox = PublicationOutbox(
        cluster_id=cluster.id,
        operation_type="initial",
        track=track,
        payload_hash=_hash_text(str(ai_result.model_dump())),
        rendered_text_hash=_hash_text(rendered_html),
        payload_preview=rendered_html[:500],
        status=status,
    )
    session.add(outbox)
    return outbox


def cleanup_stuck_outbox(session: Session) -> int:
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.OUTBOX_LOCK_TIMEOUT_MINUTES)
    stuck = session.scalars(
        select(PublicationOutbox).where(
            PublicationOutbox.status == "sending",
            PublicationOutbox.locked_at < cutoff,
        )
    ).all()
    count = 0
    for item in stuck:
        if item.send_started_at and not session.query(Publication).filter_by(outbox_id=item.id).first():
            item.status = "unknown"
        else:
            item.status = "pending"
        item.locked_at = None
        count += 1
    return count


def process_outbox_item(session: Session, outbox_id: int) -> bool:
    settings = get_settings()
    if settings.PUBLISH_MODE == "dry_run":
        return False

    with outbox_lock(session, outbox_id) as outbox:
        if outbox.status not in ("pending", "failed"):
            return False
        outbox.status = "sending"
        outbox.locked_at = datetime.now(timezone.utc)
        outbox.send_started_at = datetime.now(timezone.utc)
        session.flush()

        cluster = session.get(Cluster, outbox.cluster_id)
        if not cluster:
            outbox.status = "failed"
            outbox.error_message = "cluster not found"
            return False

        from app.db.models.ai_result import AIResult
        from app.ai.schemas import AIClusterOutput

        ai_row = session.scalars(
            select(AIResult)
            .where(AIResult.cluster_id == cluster.id)
            .order_by(AIResult.created_at.desc())
            .limit(1)
        ).first()
        if not ai_row:
            outbox.status = "failed"
            outbox.error_message = "no ai result"
            return False

        ai_result = AIClusterOutput(
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
        rendered = format_publication_html(session, cluster.id, ai_result)
        mode = settings.PUBLISH_MODE
        chat_id = get_cached_chat_id(mode)
        if not chat_id:
            chat_id = resolve_and_cache_chat(mode)

        try:
            post_id = send_message_html(chat_id, rendered)
            pub = Publication(
                cluster_id=cluster.id,
                outbox_id=outbox.id,
                telegram_post_id=post_id,
                track=outbox.track,
                published_at=datetime.now(timezone.utc),
            )
            session.add(pub)
            outbox.status = "sent"
            cluster.status = "published"
            write_audit_log(
                session,
                entity_type="cluster",
                entity_id=cluster.id,
                action="published",
                actor="publish_task",
                old_status="ai_done",
                new_status="published",
            )
            return True
        except Exception as exc:
            outbox.status = "failed"
            outbox.error_message = str(exc)[:500]
            write_audit_log(
                session,
                entity_type="outbox",
                entity_id=outbox.id,
                action="publish_failed",
                actor="publish_task",
                reason="telegram_flood_exhausted" if "429" in str(exc) else None,
                metadata={"error": str(exc)[:200]},
            )
            return False
