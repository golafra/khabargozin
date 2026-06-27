"""Independent source counting — lineage analysis."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clustering.embedder import text_similarity
from app.config import get_settings
from app.db.models.message import Message
from app.db.models.source import Source


def _is_forwarded(msg: Message) -> bool:
    payload = msg.raw_payload or {}
    if payload.get("forward_from") or payload.get("fwd_from"):
        return True
    if payload.get("forward_from_chat") or payload.get("forward_from_message_id"):
        return True
    return False


def recalculate_independent_sources(session: Session, cluster_id: int) -> int:
    """
    Count independent sources — never use distinct_sources for decisions.
    Primary sources count as independent. Non-primary similar to primary = republish.
    """
    settings = get_settings()
    rows = session.execute(
        select(Message, Source)
        .join(Source, Message.source_id == Source.id)
        .where(Message.cluster_id == cluster_id)
        .where(Message.is_deleted.is_(False))
    ).all()

    if not rows:
        return 0

    primaries = [(m, s) for m, s in rows if s.is_primary_source]
    non_primaries = [(m, s) for m, s in rows if not s.is_primary_source]

    independent_lineages: set[str] = set()

    for msg, src in primaries:
        independent_lineages.add(f"primary:{src.id}")

    for msg, src in non_primaries:
        text = msg.text or ""
        if _is_forwarded(msg):
            matched_primary = False
            for p_msg, p_src in primaries:
                independent_lineages.add(f"primary:{p_src.id}")
                matched_primary = True
                break
            if matched_primary:
                continue

        matched_primary = False
        for p_msg, p_src in primaries:
            p_text = p_msg.text or ""
            if text and p_text and text_similarity(text, p_text) > settings.REPUBLISH_SIM_THRESHOLD:
                independent_lineages.add(f"primary:{p_src.id}")
                matched_primary = True
                break
        if not matched_primary:
            independent_lineages.add(f"source:{src.id}")

    return len(independent_lineages)


def independent_lineage_diversity(session: Session, cluster_id: int) -> float:
    """Ratio of independent sources to distinct sources (0..1)."""
    distinct = distinct_source_count(session, cluster_id)
    if distinct == 0:
        return 0.0
    independent = recalculate_independent_sources(session, cluster_id)
    return min(1.0, independent / distinct)


def distinct_source_count(session: Session, cluster_id: int) -> int:
    result = session.execute(
        select(Source.id)
        .join(Message, Message.source_id == Source.id)
        .where(Message.cluster_id == cluster_id)
        .distinct()
    ).scalars().all()
    return len(result)
