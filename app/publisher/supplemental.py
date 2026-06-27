"""Supplemental updates — phase 2."""

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.client import AIClient
from app.audit import write_audit_log
from app.config import get_settings
from app.db.models.ai_result import AIResult
from app.db.models.publication import Publication
from app.db.models.publication_outbox import PublicationOutbox
from app.publisher.bot import edit_message_html, resolve_chat_id, send_message_html
from app.publisher.formatter import format_publication_html
from app.ai.schemas import AIClusterOutput
from app.resilience.locking import publication_lock


def process_supplemental(session: Session, cluster_id: int, new_text: str) -> bool:
    from app.clustering.conflict_detector import detect_critical_numeric_changes
    from app.db.models.cluster import Cluster
    from app.db.models.message import Message

    settings = get_settings()
    cluster = session.get(Cluster, cluster_id)
    pub = session.scalars(
        select(Publication).where(Publication.cluster_id == cluster_id).order_by(Publication.published_at.desc())
    ).first()
    if not pub or pub.is_retracted:
        return False

    ai_row = session.scalars(
        select(AIResult).where(AIResult.cluster_id == cluster_id).order_by(AIResult.created_at.desc())
    ).first()
    if not ai_row:
        return False

    old_texts = [
        m.text or ""
        for m in session.scalars(
            select(Message).where(Message.cluster_id == cluster_id)
        ).all()
    ]
    numeric_deltas = detect_critical_numeric_changes(old_texts, new_text)
    if numeric_deltas and cluster:
        cluster.story_phase = "developing"
        cluster.locked_for_hold = True
        cluster.status = "hold"
        write_audit_log(
            session,
            entity_type="cluster",
            entity_id=cluster_id,
            action="numeric_delta_hold",
            actor="supplemental",
            reason="critical_numeric_changes",
            metadata={"deltas": [d.__dict__ for d in numeric_deltas]},
        )
        return False

    published_text = f"{ai_row.headline}\n{ai_row.summary}"
    client = AIClient(session)
    try:
        delta = client.delta_check(published_text, new_text)
    except Exception:
        return False

    if not delta.has_new_value:
        write_audit_log(
            session,
            entity_type="cluster",
            entity_id=cluster_id,
            action="supplement_dropped",
            actor="supplemental",
            reason="supplement_no_value",
        )
        return False

    with publication_lock(session, pub.id):
        ai_result = AIClusterOutput(
            status=ai_row.status,
            editorial_priority=ai_row.editorial_priority,
            confidence=ai_row.confidence,
            headline=ai_row.headline,
            summary=ai_row.summary,
            body=ai_row.body or "",
            why_it_matters=ai_row.why_it_matters,
            conflicts=ai_row.conflicts or [],
            sources_used=ai_row.sources_used or [],
            rejection_reason=ai_row.rejection_reason,
            sensitivity=ai_row.sensitivity,
            needs_human_review=ai_row.needs_human_review,
        )
        base_html = format_publication_html(session, cluster_id, ai_result)
        supplement = f"\n\n[بخش تکمیلی]\n{delta.supplement_text}"
        rendered = base_html + supplement

        event_key = hashlib.sha256(
            f"{cluster_id}:supplement:{new_text[:100]}".encode()
        ).hexdigest()[:32]

        existing = session.scalar(
            select(PublicationOutbox).where(
                PublicationOutbox.cluster_id == cluster_id,
                PublicationOutbox.operation_type == "supplemental",
                PublicationOutbox.event_key == event_key,
            )
        )
        if existing:
            return False

        outbox = PublicationOutbox(
            cluster_id=cluster_id,
            operation_type="supplemental",
            event_key=event_key,
            track="batch",
            payload_hash=hashlib.sha256(rendered.encode()).hexdigest(),
            rendered_text_hash=hashlib.sha256(rendered.encode()).hexdigest(),
            payload_preview=rendered[:500],
            status="pending",
        )
        session.add(outbox)

        chat_id = resolve_chat_id(settings.PUBLISH_MODE)
        if chat_id and pub.telegram_post_id and settings.PUBLISH_MODE != "dry_run":
            edit_message_html(chat_id, pub.telegram_post_id, rendered)
            send_message_html(chat_id, "جزئیات جدید به متن خبر اضافه شد.")

        outbox.status = "sent"
        write_audit_log(
            session,
            entity_type="cluster",
            entity_id=cluster_id,
            action="supplemental_published",
            actor="supplemental",
        )
        return True
