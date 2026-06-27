"""Anchor message selection for clusters."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clustering.embedder import embed_text, embedding_to_list
from app.db.models.cluster import Cluster
from app.db.models.message import Message
from app.db.models.source import Source


def completeness_score(text: str) -> float:
    if not text:
        return 0.0
    length = len(text.strip())
    if length < 80:
        return 0.3
    if length < 200:
        return 0.6
    if length < 500:
        return 0.85
    return 1.0


def recency_score(published_at: datetime | None) -> float:
    if not published_at:
        return 0.5
    now = datetime.now(timezone.utc)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_h = (now - published_at).total_seconds() / 3600.0
    return max(0.0, 1.0 - age_h / 12.0)


def text_length_score(length: int) -> float:
    return min(1.0, length / 400.0)


def anchor_score(message: Message, source: Source) -> float:
    text = message.text or ""
    return (
        0.35 * min(source.credibility_weight / 1.5, 1.0)
        + 0.25 * completeness_score(text)
        + 0.25 * recency_score(message.published_at)
        + 0.15 * text_length_score(len(text))
    )


def select_best_anchor(session: Session, cluster_id: int) -> Message | None:
    rows = session.execute(
        select(Message, Source)
        .join(Source, Message.source_id == Source.id)
        .where(Message.cluster_id == cluster_id, Message.is_deleted.is_(False))
    ).all()
    if not rows:
        return None
    best_msg, _ = max(rows, key=lambda pair: anchor_score(pair[0], pair[1]))
    return best_msg


def update_cluster_anchor(session: Session, cluster: Cluster) -> None:
    best = select_best_anchor(session, cluster.id)
    if not best:
        return
    current_id = cluster.anchor_message_id
    if current_id == best.id:
        return

    if current_id:
        current = session.get(Message, current_id)
        current_src = session.get(Source, current.source_id) if current else None
        best_src = session.get(Source, best.source_id)
        if current and current_src and best_src:
            if anchor_score(current, current_src) >= anchor_score(best, best_src):
                return

    cluster.anchor_message_id = best.id
    emb = embedding_to_list(best.embedding)
    if emb is None and best.text:
        emb = embed_text(best.text)
        best.embedding = emb
    if emb is not None:
        cluster.centroid_embedding = emb


def get_anchor_message(session: Session, cluster_id: int) -> Message | None:
    cluster = session.get(Cluster, cluster_id)
    if cluster and cluster.anchor_message_id:
        msg = session.get(Message, cluster.anchor_message_id)
        if msg:
            return msg
    return session.scalars(
        select(Message)
        .where(Message.cluster_id == cluster_id)
        .order_by(Message.published_at.asc())
        .limit(1)
    ).first()
