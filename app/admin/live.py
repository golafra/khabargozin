"""Live snapshot for admin polling — recent messages + merge context."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.admin.helpers import message_times
from app.admin.operations import list_recent_publications
from app.config import get_settings
from app.db.models.ai_result import AIResult
from app.db.models.audit_log import AuditLog
from app.db.models.cluster import Cluster
from app.db.models.message import Message
from app.db.models.source import Source


def _preview(text: str | None, n: int = 160) -> str:
    t = (text or "").replace("\n", " ").strip()
    return t[:n] + ("…" if len(t) > n else "")


def get_live_snapshot(session: Session, *, feed_hours: float = 2, feed_limit: int = 50) -> dict:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=feed_hours)
    hour_ago = now - timedelta(hours=1)
    fresh_cutoff = now - timedelta(minutes=20)
    telegram_fresh_cutoff = now - timedelta(minutes=45)

    latest_message_at = session.scalar(select(func.max(Message.created_at)))

    unclustered = session.scalar(
        select(func.count()).select_from(Message).where(Message.cluster_id.is_(None))
    ) or 0
    fetched_hour = session.scalar(
        select(func.count()).select_from(Message).where(Message.created_at >= hour_ago)
    ) or 0
    clustered_hour = session.scalar(
        select(func.count())
        .select_from(Message)
        .where(Message.created_at >= hour_ago, Message.cluster_id.isnot(None))
    ) or 0

    sources_rows = session.scalars(select(Source).order_by(Source.username)).all()
    sources = [
        {
            "username": s.username,
            "active": s.is_active,
            "last_fetch": s.last_successful_fetch_at.isoformat() if s.last_successful_fetch_at else None,
            "errors": s.fetch_error_count,
            "stale": bool(
                s.last_successful_fetch_at
                and s.last_successful_fetch_at
                < now - timedelta(minutes=settings.SOURCE_STALE_ALERT_MINUTES)
            )
            if s.last_successful_fetch_at
            else True,
        }
        for s in sources_rows
    ]

    msg_rows = session.execute(
        select(Message, Source, Cluster)
        .join(Source, Message.source_id == Source.id)
        .outerjoin(Cluster, Message.cluster_id == Cluster.id)
        .where(Message.created_at >= since)
        .order_by(func.coalesce(Message.published_at, Message.created_at).desc())
        .limit(feed_limit)
    ).all()

    feed_mode = "recent"
    if not msg_rows:
        feed_mode = "archive"
        msg_rows = session.execute(
            select(Message, Source, Cluster)
            .join(Source, Message.source_id == Source.id)
            .outerjoin(Cluster, Message.cluster_id == Cluster.id)
            .order_by(func.coalesce(Message.published_at, Message.created_at).desc())
            .limit(feed_limit)
        ).all()

    fresh_count = session.scalar(
        select(func.count()).select_from(Message).where(Message.created_at >= fresh_cutoff)
    ) or 0

    feed: list[dict] = []
    for message, source, cluster in msg_rows:
        audit = session.scalar(
            select(AuditLog)
            .where(AuditLog.entity_type == "message", AuditLog.entity_id == message.id)
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
        meta = (audit.metadata_ or {}) if audit else {}
        action = audit.action if audit else ("pending_cluster" if not message.cluster_id else "clustered")

        compared: list[dict] = []
        if meta.get("candidates"):
            compared = meta["candidates"]
        elif meta.get("compared_candidates"):
            compared = meta["compared_candidates"]

        cluster_peers: list[dict] = []
        if message.cluster_id:
            peers = session.execute(
                select(Message, Source)
                .join(Source, Message.source_id == Source.id)
                .where(
                    Message.cluster_id == message.cluster_id,
                    Message.id != message.id,
                )
                .order_by(Message.published_at.asc())
                .limit(4)
            ).all()
            cluster_peers = [
                {"source": src.username, "preview": _preview(msg.text, 100)}
                for msg, src in peers
            ]

        ai_headline = None
        if cluster:
            ai = session.scalar(
                select(AIResult)
                .where(AIResult.cluster_id == cluster.id)
                .order_by(AIResult.created_at.desc())
                .limit(1)
            )
            if ai:
                ai_headline = _preview(ai.headline, 80)

        times = message_times(message)
        is_fresh = bool(
            (message.created_at and message.created_at >= fresh_cutoff)
            or (message.published_at and message.published_at >= telegram_fresh_cutoff)
        )
        feed.append(
            {
                "id": message.id,
                "source": source.username,
                "text": _preview(message.text, 200),
                "is_fresh": is_fresh,
                "fetched_at": times["fetched_at"],
                "fetched_fmt": times["fetched_fmt"],
                "telegram_published": times["telegram_published"],
                "telegram_published_fmt": times["telegram_published_fmt"],
                "telegram_edited": times["telegram_edited"],
                "telegram_edited_fmt": times["telegram_edited_fmt"],
                "has_edit": times["has_edit"],
                "cluster_id": message.cluster_id,
                "cluster_status": cluster.status if cluster else None,
                "cluster_score": round(cluster.cluster_score, 2) if cluster and cluster.cluster_score else None,
                "independent_sources": cluster.independent_source_count if cluster else 0,
                "action": action,
                "similarity": meta.get("similarity") or meta.get("best_similarity"),
                "match_reason": meta.get("match_reason"),
                "compared": compared[:4],
                "cluster_peers": cluster_peers,
                "ai_headline": ai_headline,
            }
        )

    status_by_cluster = dict(
        session.execute(select(Cluster.status, func.count()).group_by(Cluster.status)).all()
    )

    return {
        "updated_at": now.isoformat(),
        "latest_message_at": latest_message_at.isoformat() if latest_message_at else None,
        "fresh_count": fresh_count,
        "publish_mode": settings.PUBLISH_MODE,
        "beat_fetch_sec": settings.BEAT_FETCH_INTERVAL_SECONDS,
        "fetch_mode": "round_robin",
        "beat_cluster_sec": settings.BEAT_CLUSTER_INTERVAL_SECONDS,
        "merge_window_h": settings.CLUSTER_ACTIVE_WINDOW_MINUTES / 60,
        "unclustered": unclustered,
        "fetched_last_hour": fetched_hour,
        "clustered_last_hour": clustered_hour,
        "clusters_by_status": status_by_cluster,
        "sources": sources,
        "feed": feed,
        "feed_empty": len(feed) == 0,
        "feed_mode": feed_mode,
        "feed_hours": feed_hours,
        "messages_total": session.scalar(select(func.count()).select_from(Message)) or 0,
        "published_recent": list_recent_publications(session, limit=10),
    }
