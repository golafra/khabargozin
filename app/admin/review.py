"""Active learning — human review feedback."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.cluster import Cluster
from app.db.models.message import Message
from app.db.models.review_feedback import ReviewFeedback

REJECT_ACTIONS = frozenset({"reject_merge", "reject_publish", "split"})
REJECT_REASONS = frozenset(
    {"topic_mismatch", "location_mismatch", "time_mismatch", "duplicate", "low_quality", "other"}
)


class ReviewValidationError(Exception):
    """Invalid review payload."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def validate_review(action: str, reject_reason: str | None) -> None:
    if action in REJECT_ACTIONS and not reject_reason:
        raise ReviewValidationError("reject_reason is required for this action")
    if reject_reason and reject_reason not in REJECT_REASONS:
        raise ReviewValidationError(f"Invalid reject_reason: {reject_reason}")


def submit_review(
    session: Session,
    cluster_id: int,
    action: str,
    *,
    reviewer: str = "admin",
    message_ids: list[int] | None = None,
    correct_cluster_id: int | None = None,
    reject_reason: str | None = None,
    reject_note: str = "",
    metadata: dict[str, Any] | None = None,
) -> ReviewFeedback:
    cluster = session.get(Cluster, cluster_id)
    if not cluster:
        raise ReviewValidationError("Cluster not found", status_code=404)

    validate_review(action, reject_reason)

    if message_ids is None:
        message_ids = list(
            session.scalars(select(Message.id).where(Message.cluster_id == cluster_id)).all()
        )

    meta = dict(metadata or {})
    if reject_reason:
        meta["reject_reason"] = reject_reason
    if reject_note:
        meta["reject_note"] = reject_note

    row = ReviewFeedback(
        cluster_id=cluster_id,
        reviewer=reviewer,
        action=action,
        message_ids=message_ids,
        correct_cluster_id=correct_cluster_id,
        metadata_=meta,
    )
    session.add(row)

    if action in REJECT_ACTIONS:
        cluster.status = "rejected"
        cluster.status_reason = reject_reason or action
        cluster.locked_for_hold = False

    session.commit()
    return row
