"""Merge to published clusters — prevent duplicate publications."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.clustering.event_signature import build_event_signature, event_signature_overlap
from app.clustering.ner import ner_overlap
from app.clustering.topic_overlap import should_merge_published, topic_overlap
from app.clustering.vector_search import find_recent_published_similar
from app.config import get_settings
from app.db.models.cluster import Cluster
from app.db.models.message import Message


def find_published_merge_target(
    session: Session,
    message: Message,
    query_embedding: list[float],
) -> int | None:
    settings = get_settings()
    candidates = find_recent_published_similar(session, query_embedding, limit=8)
    text = message.text or ""
    now = datetime.now(timezone.utc)
    msg_signature = build_event_signature(text)

    for cluster_id, sim in candidates:
        cluster = session.get(Cluster, cluster_id)
        if not cluster or cluster.status != "published":
            continue
        if cluster.window_end and (now - cluster.window_end) > timedelta(
            minutes=settings.SUPPLEMENT_MAX_DELTA_MINUTES
        ):
            continue

        sample = session.query(Message).filter_by(cluster_id=cluster_id).first()
        sample_text = sample.text if sample else ""
        ner_val = ner_overlap(text, sample_text) if text and sample_text else 0.0
        event_overlap = event_signature_overlap(msg_signature, cluster.event_signature)

        if not should_merge_published(sim, text, sample_text, ner_boost=ner_val):
            continue
        if event_overlap < settings.MERGE_EVENT_SIG and topic_overlap(text, sample_text) < settings.MERGE_TOPIC_OVERLAP:
            continue
        return cluster_id
    return None
