"""Shared post-AI routing — enqueue outbox and optional fast publish."""

from sqlalchemy.orm import Session

from app.ai.guardrails import check_guardrails
from app.ai.schemas import AIClusterOutput
from app.audit import write_audit_log
from app.config import get_settings
from app.db.models.cluster import Cluster
from app.publisher.formatter import format_publication_html
from app.publisher.outbox import enqueue_initial, process_outbox_item
from app.publisher.tracks import route_track


def apply_publish_routing(
    session: Session,
    cluster: Cluster,
    result: AIClusterOutput,
    *,
    locked_for_hold: bool = False,
) -> str:
    """Route cluster after AI. Returns track name or 'rejected'."""
    settings = get_settings()
    ok, guard_reason = check_guardrails(result, cluster.independent_source_count)
    track = route_track(
        session,
        result,
        cluster.independent_source_count,
        locked_for_hold=locked_for_hold,
    )

    if not ok:
        cluster.status = "rejected"
        cluster.status_reason = guard_reason or "sensitivity_guardrail_fail"
        write_audit_log(
            session,
            entity_type="cluster",
            entity_id=cluster.id,
            action="ai_rejected",
            actor="routing",
            reason="sensitivity_guardrail_fail",
            old_status="ai_ready",
            new_status="rejected",
        )
        return "rejected"

    if track == "reject":
        cluster.status = "rejected"
        cluster.status_reason = result.rejection_reason or "ai_reject"
        write_audit_log(
            session,
            entity_type="cluster",
            entity_id=cluster.id,
            action="ai_rejected",
            actor="routing",
            reason="ai_reject",
            old_status="ai_ready",
            new_status="rejected",
        )
        return "reject"

    cluster.status = "ai_done"
    rendered = format_publication_html(session, cluster.id, result)
    outbox = enqueue_initial(session, cluster, result, rendered, track)

    if track == "fast" and settings.PUBLISH_MODE != "dry_run" and outbox:
        process_outbox_item(session, outbox.id)

    return track
