"""Audit logging helper."""

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models.audit_log import AuditLog


def write_audit_log(
    session: Session,
    *,
    entity_type: str,
    entity_id: Optional[int],
    action: str,
    actor: str,
    reason: Optional[str] = None,
    old_status: Optional[str] = None,
    new_status: Optional[str] = None,
    source_snapshot: Optional[dict[str, Any]] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> AuditLog:
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        reason=reason,
        old_status=old_status,
        new_status=new_status,
        actor=actor,
        source_snapshot=source_snapshot,
        decision_version=get_settings().DECISION_VERSION,
        metadata_=metadata,
    )
    session.add(entry)
    return entry
