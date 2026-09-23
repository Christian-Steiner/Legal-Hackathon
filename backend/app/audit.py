"""Append-only audit log. Every ingest, match, draft, edit and decision goes through log()."""
from sqlalchemy.orm import Session

from app.models import AuditLogEntry


def log(
    db: Session,
    *,
    actor: str,
    action: str,
    object_type: str,
    object_id: str | int,
    details: dict | None = None,
) -> AuditLogEntry:
    """Add an audit entry to the session. The caller commits together with the change itself,
    so a change and its audit entry are never persisted separately."""
    entry = AuditLogEntry(
        actor=actor,
        action=action,
        object_type=object_type,
        object_id=str(object_id),
        details=details or {},
    )
    db.add(entry)
    return entry
