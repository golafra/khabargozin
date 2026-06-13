"""Merge to published clusters — phase 2 / Sprint G."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.clustering.event_signature import event_signature_overlap
from app.clustering.ner import ner_overlap
from app.clustering.vector_search import find_similar_clusters
from app.config import get_settings
from app.db.models.cluster import Cluster
from app.db.models.message import Message


def find_published_merge_target(
    session: Session,
    message: Message,
    query_embedding: list[float],
) -> int | None:
    settings = get_settings()
    candidates = find_similar_clusters(
        session, query_embedding, statuses=("published",), limit=5
    )
    text = message.text or ""
    now = datetime.now(timezone.utc)

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
        event_overlap = event_signature_overlap(
            cluster.event_signature,
            cluster.event_signature,
        )

        required_sim = settings.MERGE_PUBLISHED_SIM
        if ner_val < settings.MERGE_PUBLISHED_NER:
            required_sim = settings.MERGE_PUBLISHED_SIM_HIGH

        if sim < required_sim:
            continue
        if ner_val < settings.MERGE_PUBLISHED_NER and sim < settings.MERGE_PUBLISHED_SIM_HIGH:
            continue
        if event_overlap < settings.MERGE_EVENT_SIG and sim < settings.MERGE_PUBLISHED_SIM_HIGH:
            continue
        return cluster_id
    return None
