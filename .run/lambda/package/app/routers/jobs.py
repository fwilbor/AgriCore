from datetime import date

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import audit, storage
from ..deps import AdminOrFarmHand, AdminUser, CurrentUser, DbSession
from ..enums import EquipmentStatus, JobPriority, JobStatus, Role, FINISHED_JOB_STATUSES
from ..models import Equipment, FieldJob, User
from ..schemas import FieldJobCreate, FieldJobOut, FieldJobStatusUpdate, FieldJobUpdate
from ..utils import apply_updates, describe, get_or_404

router = APIRouter(prefix="/jobs", tags=["field jobs"])

JOB_LOAD_OPTIONS = (
    selectinload(FieldJob.equipment).selectinload(Equipment.farm),
    selectinload(FieldJob.operator),
    selectinload(FieldJob.service_reports),
)


def get_job_for_user(db: Session, job_id: int, user: User) -> FieldJob:
    """Load a job, hiding other people's jobs from Farm Hands (404, not 403,
    so they can't even confirm the job exists)."""
    job = get_or_404(db, FieldJob, job_id)
    if user.role == Role.FARM_HAND and job.operator_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"FieldJob {job_id} not found")
    return job


def sync_equipment_status(db: Session, job: FieldJob) -> None:
    """Business rule: starting a job puts the machine In-Use; finishing the
    last running job on it returns the machine to Idle."""
    equipment = job.equipment
    if job.status == JobStatus.IN_PROGRESS and equipment.status == EquipmentStatus.IDLE:
        equipment.status = EquipmentStatus.IN_USE
    elif job.status in FINISHED_JOB_STATUSES and equipment.status == EquipmentStatus.IN_USE:
        still_running = db.scalar(
            select(FieldJob.id).where(
                FieldJob.equipment_id == equipment.id,
                FieldJob.status == JobStatus.IN_PROGRESS,
                FieldJob.id != job.id,
            )
        )
        if not still_running:
            equipment.status = EquipmentStatus.IDLE


@router.get("", response_model=list[FieldJobOut])
def list_jobs(
    db: DbSession,
    user: CurrentUser,
    status_filter: JobStatus | None = Query(None, alias="status"),
    priority: JobPriority | None = None,
    equipment_id: int | None = None,
):
    stmt = select(FieldJob).options(*JOB_LOAD_OPTIONS).order_by(FieldJob.id.desc())
    if user.role == Role.FARM_HAND:
        stmt = stmt.where(FieldJob.operator_id == user.id)
    if status_filter:
        stmt = stmt.where(FieldJob.status == status_filter)
    if priority:
        stmt = stmt.where(FieldJob.priority == priority)
    if equipment_id:
        stmt = stmt.where(FieldJob.equipment_id == equipment_id)
    return db.scalars(stmt).all()


@router.get("/{job_id}", response_model=FieldJobOut)
def get_job(job_id: int, db: DbSession, user: CurrentUser):
    return get_job_for_user(db, job_id, user)


@router.post("", response_model=FieldJobOut, status_code=status.HTTP_201_CREATED)
def create_job(payload: FieldJobCreate, db: DbSession, admin: AdminUser):
    equipment = get_or_404(db, Equipment, payload.equipment_id)
    if equipment.status == EquipmentStatus.RETIRED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cannot schedule work on retired equipment")
    job = FieldJob(**payload.model_dump())
    job.scheduled_date = job.scheduled_date or date.today()
    db.add(job)
    db.flush()
    sync_equipment_status(db, job)
    audit.record(db, admin, "CREATE", "field_job", job.id, job.title)
    db.commit()
    db.refresh(job)
    return job


@router.patch("/{job_id}", response_model=FieldJobOut)
def update_job(job_id: int, payload: FieldJobUpdate, db: DbSession, admin: AdminUser):
    job = get_or_404(db, FieldJob, job_id)
    changes = apply_updates(job, payload)
    db.flush()
    db.refresh(job)  # reload relationships if equipment_id changed
    sync_equipment_status(db, job)
    audit.record(db, admin, "UPDATE", "field_job", job.id, describe(changes))
    db.commit()
    db.refresh(job)
    return job


@router.patch("/{job_id}/status", response_model=FieldJobOut)
def change_job_status(
    job_id: int, payload: FieldJobStatusUpdate, db: DbSession, user: AdminOrFarmHand
):
    """Farm Hands' main action. Admins may also use it."""
    job = get_job_for_user(db, job_id, user)
    if user.role == Role.FARM_HAND and job.status in FINISHED_JOB_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Job is already {job.status.value}; ask an admin to reopen it"
        )
    old = job.status
    job.status = payload.status
    sync_equipment_status(db, job)
    audit.record(
        db, user, "STATUS_CHANGE", "field_job", job.id, f"{old.value} -> {payload.status.value}"
    )
    db.commit()
    db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: int, db: DbSession, admin: AdminUser):
    job = get_or_404(db, FieldJob, job_id)
    keys = [r.file_key for r in job.service_reports]
    audit.record(db, admin, "DELETE", "field_job", job.id, job.title)
    db.delete(job)  # service_reports rows go too (cascade="all, delete-orphan")
    db.commit()
    for key in keys:  # then tidy up the files in S3
        storage.delete_file(key)
