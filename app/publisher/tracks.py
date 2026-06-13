"""Fast / Batch / Reject track routing."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.guardrails import check_guardrails
from app.ai.schemas import AIClusterOutput
from app.config import get_settings
from app.db.models.hold_queue import HoldQueue
from app.db.models.publication_outbox import PublicationOutbox


def route_track(
    session: Session,
    result: AIClusterOutput,
    independent_source_count: int,
    *,
    locked_for_hold: bool = False,
) -> str:
    settings = get_settings()

    if locked_for_hold:
        return "hold"

    if result.status == "reject" or result.confidence < settings.REJECT_CONFIDENCE:
        return "reject"

    ok, _ = check_guardrails(result, independent_source_count)
    if not ok:
        return "reject"

    if (
        result.status == "publish"
        and result.editorial_priority == 5
        and independent_source_count >= 2
        and not result.conflicts
        and result.confidence >= settings.FAST_MIN_CONFIDENCE
    ):
        return "fast"

    if (
        result.status == "publish"
        and result.editorial_priority in (3, 4)
        and result.confidence >= settings.BATCH_MIN_CONFIDENCE
    ):
        return "batch"

    if result.status == "publish" and result.confidence >= settings.BATCH_MIN_CONFIDENCE:
        return "batch"

    return "reject"


def batch_interval_minutes(session: Session) -> int:
    settings = get_settings()
    queue_len = session.scalar(
        select(func.count())
        .select_from(PublicationOutbox)
        .where(PublicationOutbox.track == "batch")
        .where(PublicationOutbox.status == "pending")
    ) or 0
    if queue_len >= settings.BATCH_QUEUE_BUSY_THRESHOLD:
        return settings.BATCH_PUBLISH_INTERVAL_BUSY_MINUTES
    return settings.BATCH_PUBLISH_INTERVAL_MINUTES


def is_in_hold_queue(session: Session, cluster_id: int) -> bool:
    return session.query(HoldQueue).filter_by(cluster_id=cluster_id).first() is not None
