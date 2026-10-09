from fastapi import APIRouter, Query
from sqlalchemy import or_, select

from ..deps import AdminOrAuditor, DbSession
from ..models import AuditLog
from ..schemas import AuditLogOut

router = APIRouter(prefix="/audit-logs", tags=["audit log"])


@router.get("", response_model=list[AuditLogOut])
def list_audit_logs(
    db: DbSession,
    _: AdminOrAuditor,
    search: str | None = None,
    action: str | None = None,
    limit: int = Query(500, ge=1, le=2000),
):
    """Searchable system log - the Auditor's main tool."""
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit)
    if action:
        stmt = stmt.where(AuditLog.action == action.upper())
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                AuditLog.user_email.ilike(like),
                AuditLog.detail.ilike(like),
                AuditLog.entity_type.ilike(like),
            )
        )
    return db.scalars(stmt).all()
