"""Operational admin queries and actions."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.helpers import action_label_fa, message_times
from app.config import get_settings
from app.db.models.ai_result import AIResult
from app.db.models.audit_log import AuditLog
from app.db.models.cluster import Cluster
from app.db.models.message import Message
from app.db.models.publication import Publication
from app.db.models.publication_outbox import PublicationOutbox
from app.db.models.source import Source


def toggle_source_active(session: Session, source_id: int) -> Source | None:
    source = session.get(Source, source_id)
    if not source:
        return None
    source.is_active = not source.is_active
    session.commit()
    return source


def _message_audit(session: Session, message_id: int) -> AuditLog | None:
    return session.scalar(
        select(AuditLog)
        .where(AuditLog.entity_type == "message", AuditLog.entity_id == message_id)
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    )


def _cluster_audits(session: Session, cluster_id: int, message_ids: list[int]) -> list[AuditLog]:
    if not message_ids:
        return list(
            session.scalars(
                select(AuditLog)
                .where(AuditLog.entity_type == "cluster", AuditLog.entity_id == cluster_id)
                .order_by(AuditLog.created_at.asc())
            ).all()
        )
    return list(
        session.scalars(
            select(AuditLog)
            .where(
                (AuditLog.entity_type == "cluster") & (AuditLog.entity_id == cluster_id)
                | ((AuditLog.entity_type == "message") & AuditLog.entity_id.in_(message_ids))
            )
            .order_by(AuditLog.created_at.asc())
        ).all()
    )


def get_cluster_story(session: Session, cluster_id: int) -> dict | None:
    """Full operational story: messages, merge mechanism, pipeline timeline."""
    cluster = session.get(Cluster, cluster_id)
    if not cluster:
        return None

    settings = get_settings()
    messages = session.execute(
        select(Message, Source)
        .join(Source, Message.source_id == Source.id)
        .where(Message.cluster_id == cluster_id)
        .order_by(Message.published_at.asc())
    ).all()

    message_rows = []
    for msg, src in messages:
        audit = _message_audit(session, msg.id)
        meta = (audit.metadata_ or {}) if audit else {}
        message_rows.append(
            {
                "id": msg.id,
                "source": src.username,
                "text": msg.text or "",
                "times": message_times(msg),
                "action": audit.action if audit else None,
                "action_label": action_label_fa(audit.action if audit else None),
                "similarity": meta.get("similarity") or meta.get("best_similarity"),
                "match_reason": meta.get("match_reason"),
                "candidates": meta.get("candidates") or meta.get("compared_candidates") or [],
                "merged_into": audit.new_status if audit and "merge" in (audit.action or "") else None,
            }
        )

    cluster_events = _cluster_audits(session, cluster_id, [m.id for m, _ in messages])

    timeline = []
    for msg_row in message_rows:
        if msg_row["action"]:
            timeline.append(
                {
                    "at": msg_row["times"]["fetched_fmt"],
                    "stage": "cluster",
                    "label": msg_row["action_label"],
                    "detail": f"@{msg_row['source']}",
                }
            )
    for ev in cluster_events:
        timeline.append(
            {
                "at": ev.created_at.strftime("%Y-%m-%d %H:%M:%S") if ev.created_at else "—",
                "stage": ev.action,
                "label": action_label_fa(ev.action),
                "detail": ev.reason or ev.new_status or "",
            }
        )

    ai = session.scalar(
        select(AIResult)
        .where(AIResult.cluster_id == cluster_id)
        .order_by(AIResult.created_at.desc())
        .limit(1)
    )
    outbox = session.scalar(
        select(PublicationOutbox).where(PublicationOutbox.cluster_id == cluster_id)
    )
    pub = session.scalar(select(Publication).where(Publication.cluster_id == cluster_id))

    mechanism = {
        "merge_window_hours": settings.CLUSTER_ACTIVE_WINDOW_MINUTES / 60,
        "merge_sim_threshold": settings.MERGE_OPEN_SIM,
        "score_threshold": settings.CLUSTER_SCORE_FALLBACK_THRESHOLD,
        "independent_sources": cluster.independent_source_count,
        "distinct_sources": cluster.distinct_sources,
    }

    return {
        "cluster": cluster,
        "messages": message_rows,
        "timeline": timeline,
        "mechanism": mechanism,
        "ai": ai,
        "outbox": outbox,
        "publication": pub,
    }


def list_recent_publications(session: Session, limit: int = 20) -> list[dict]:
    pubs = session.scalars(
        select(Publication).order_by(Publication.published_at.desc()).limit(limit)
    ).all()
    rows = []
    for pub in pubs:
        story = get_cluster_story(session, pub.cluster_id)
        if not story:
            continue
        ai = story["ai"]
        rows.append(
            {
                "cluster_id": pub.cluster_id,
                "output_published_at": pub.published_at.isoformat() if pub.published_at else None,
                "output_published_fmt": pub.published_at.strftime("%Y-%m-%d %H:%M:%S")
                if pub.published_at
                else "—",
                "telegram_post_id": pub.telegram_post_id,
                "track": pub.track,
                "headline": ai.headline if ai else "—",
                "summary": (ai.summary[:200] + "…") if ai and len(ai.summary) > 200 else (ai.summary if ai else ""),
                "confidence": ai.confidence if ai else None,
                "independent_sources": story["cluster"].independent_source_count,
                "message_count": len(story["messages"]),
                "sources": list({m["source"] for m in story["messages"]}),
                "mechanism": story["mechanism"],
                "messages": story["messages"],
            }
        )
    return rows
