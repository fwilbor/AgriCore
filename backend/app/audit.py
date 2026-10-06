"""Tiny helper that appends a row to the audit log.

It only *adds* the row to the session; the caller's `db.commit()` saves it in
the same transaction as the change it describes, so they succeed or fail together.
"""
from sqlalchemy.orm import Session

from .models import AuditLog, User


def record(
    db: Session,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    detail: str | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            user_email=user.email if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            detail=detail,
        )
    )
