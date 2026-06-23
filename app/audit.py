"""Audit logging helper."""

import math
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models.audit_log import AuditLog


def _sanitize_json(value: Any) -> Any:
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, dict):
        return {k: _sanitize_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_json(v) for v in value]
    return value


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
        metadata_=metadata if metadata is None else _sanitize_json(metadata),
    )
    session.add(entry)
    return entry
