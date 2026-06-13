"""Retraction detection and handling — phase 2."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.client import AIClient
from app.audit import write_audit_log
from app.config import get_settings
from app.db.models.cluster import Cluster
from app.db.models.message import Message
from app.db.models.publication import Publication
from app.publisher.bot import edit_message_html, resolve_chat_id, send_message_html
from app.ai.schemas import AIClusterOutput
from app.publisher.formatter import format_publication_html
from app.publisher.retraction_state import RetractionState
from app.resilience.locking import publication_lock

NEGATION_HINTS = ("تکذیب", "رد شد", "نادرست", "اشتباه", "اصلاح", "به‌روزرسانی")


def detect_retraction_candidates(session: Session, message: Message) -> list[int]:
    candidates: list[int] = []
    if message.reply_to_message_id:
        pub_cluster = _published_cluster_for_message(session, message.source_id, message.reply_to_message_id)
        if pub_cluster:
            candidates.append(pub_cluster)

    if message.edit_date:
        own_pub = _published_cluster_for_message(session, message.source_id, message.message_id)
        if own_pub:
            candidates.append(own_pub)

    text = (message.text or "").lower()
    if any(h in text for h in NEGATION_HINTS) and message.cluster_id:
        cluster = session.get(Cluster, message.cluster_id)
        if cluster and cluster.status == "published":
            candidates.append(cluster.id)

    return list(set(candidates))


def _published_cluster_for_message(session: Session, source_id: int, message_id: int) -> int | None:
    msg = session.scalar(
        select(Message).where(
            Message.source_id == source_id,
            Message.message_id == message_id,
        )
    )
    if msg and msg.cluster_id:
        cluster = session.get(Cluster, msg.cluster_id)
        if cluster and cluster.status == "published":
            return cluster.id
    return None


def process_retraction_candidate(session: Session, cluster_id: int, new_message: Message) -> RetractionState:
    settings = get_settings()
    pub = session.scalars(
        select(Publication).where(Publication.cluster_id == cluster_id).order_by(Publication.published_at.desc())
    ).first()
    if not pub:
        return RetractionState.IGNORE

    from app.db.models.ai_result import AIResult
    from app.ai.schemas import AIClusterOutput

    ai_row = session.scalars(
        select(AIResult).where(AIResult.cluster_id == cluster_id).order_by(AIResult.created_at.desc())
    ).first()
    published_text = ai_row.headline + "\n" + ai_row.summary if ai_row else ""
    new_text = new_message.text or ""

    client = AIClient(session)
    try:
        classification = client.classify_retraction(published_text, new_text)
    except Exception:
        return RetractionState.IGNORE

    if classification.confidence < settings.RETRACTION_MIN_CONFIDENCE:
        write_audit_log(
            session,
            entity_type="cluster",
            entity_id=cluster_id,
            action="retraction_ignored",
            actor="retraction_fsm",
            reason="confidence_too_low",
        )
        return RetractionState.IGNORE

    if classification.type == "noise":
        return RetractionState.IGNORE
    if classification.type == "update":
        return RetractionState.UPDATE

    with publication_lock(session, pub.id):
        if classification.type == "retraction":
            _apply_retraction(session, pub, ai_row, classification.corrected_text)
            return RetractionState.RETRACTION
        if classification.type == "correction":
            _apply_correction(session, pub, ai_row, classification.corrected_text)
            return RetractionState.CORRECTION

    return RetractionState.IGNORE


def _apply_retraction(session, pub: Publication, ai_row, corrected_text: str) -> None:
    settings = get_settings()
    if ai_row:
        ai_result = AIClusterOutput(
            status=ai_row.status,
            editorial_priority=ai_row.editorial_priority,
            confidence=ai_row.confidence,
            headline=f"[🔴 تکذیب شد] {ai_row.headline}",
            summary=corrected_text or ai_row.summary,
            why_it_matters=ai_row.why_it_matters,
            conflicts=ai_row.conflicts or [],
            sources_used=ai_row.sources_used or [],
            rejection_reason=ai_row.rejection_reason,
            sensitivity=ai_row.sensitivity,
            needs_human_review=ai_row.needs_human_review,
        )
        rendered = format_publication_html(session, pub.cluster_id, ai_result)
        chat_id = resolve_chat_id(settings.PUBLISH_MODE)
        if chat_id and pub.telegram_post_id:
            edit_message_html(chat_id, pub.telegram_post_id, rendered)
            send_message_html(chat_id, "تکذیب: روایت به‌روز در پست اصلی درج شد.")
    pub.is_retracted = True
    write_audit_log(
        session,
        entity_type="publication",
        entity_id=pub.id,
        action="retracted",
        actor="retraction_fsm",
        new_status="retracted",
    )


def _apply_correction(session, pub: Publication, ai_row, corrected_text: str) -> None:
    settings = get_settings()
    if ai_row and corrected_text:
        chat_id = resolve_chat_id(settings.PUBLISH_MODE)
        if chat_id and pub.telegram_post_id:
            send_message_html(chat_id, f"اصلاح: {corrected_text[:400]}")
