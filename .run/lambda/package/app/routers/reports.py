from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .. import audit, storage
from ..config import get_settings
from ..deps import AdminOrAuditor, AdminOrFarmHand, AdminUser, CurrentUser, DbSession
from ..models import ServiceReport
from ..schemas import DownloadUrlOut, ServiceReportOut
from ..utils import get_or_404
from .jobs import get_job_for_user

router = APIRouter(tags=["service reports"])


@router.get("/reports", response_model=list[ServiceReportOut])
def list_all_reports(db: DbSession, _: AdminOrAuditor):
    stmt = (
        select(ServiceReport)
        .options(selectinload(ServiceReport.uploaded_by))
        .order_by(ServiceReport.created_at.desc())
    )
    return db.scalars(stmt).all()


@router.get("/jobs/{job_id}/reports", response_model=list[ServiceReportOut])
def list_job_reports(job_id: int, db: DbSession, user: CurrentUser):
    job = get_job_for_user(db, job_id, user)
    return sorted(job.service_reports, key=lambda r: r.created_at, reverse=True)


@router.post(
    "/jobs/{job_id}/reports",
    response_model=ServiceReportOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_report(
    job_id: int,
    db: DbSession,
    user: AdminOrFarmHand,
    file: Annotated[UploadFile, File(description="Image, .txt or .pdf")],
    notes: Annotated[str | None, Form(max_length=2000)] = None,
):
    """multipart/form-data upload: the file goes to S3, its URL goes to PostgreSQL."""
    job = get_job_for_user(db, job_id, user)

    if file.content_type not in storage.ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Unsupported file type {file.content_type}. Allowed: images, .txt, .pdf",
        )
    file.file.seek(0, 2)  # jump to end to measure size
    size = file.file.tell()
    file.file.seek(0)
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    if size == 0 or size > max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File must be between 1 byte and {get_settings().max_upload_mb} MB",
        )

    filename = file.filename or "report"
    key = storage.build_key(job.id, filename)
    file_url = storage.upload_file(file.file, key, file.content_type)

    report = ServiceReport(
        field_job_id=job.id,
        file_url=file_url,
        file_key=key,
        file_name=filename,
        content_type=file.content_type,
        file_size=size,
        notes=notes,
        uploaded_by_id=user.id,
    )
    db.add(report)
    db.flush()
    audit.record(db, user, "UPLOAD", "service_report", report.id, f"job {job.id}: {filename}")
    db.commit()
    db.refresh(report)
    return report


@router.get("/reports/{report_id}/download-url", response_model=DownloadUrlOut)
def report_download_url(report_id: int, db: DbSession, user: CurrentUser):
    report = get_or_404(db, ServiceReport, report_id)
    get_job_for_user(db, report.field_job_id, user)  # same visibility rules as the job
    return DownloadUrlOut(
        url=storage.presigned_download_url(report.file_key, report.file_name),
        expires_in=get_settings().presigned_url_seconds,
    )


@router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(report_id: int, db: DbSession, admin: AdminUser):
    report = get_or_404(db, ServiceReport, report_id)
    key = report.file_key
    audit.record(db, admin, "DELETE", "service_report", report.id, report.file_name)
    db.delete(report)
    db.commit()
    storage.delete_file(key)
