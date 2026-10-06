"""SQLAlchemy 2.0 ORM models - one class per table.

`Mapped[int]` type hints tell SQLAlchemy the Python type, and
`mapped_column(...)` adds database details (keys, lengths, defaults).
`relationship(...)` lets you walk from one object to another
(`equipment.farm.name`) without writing JOINs by hand.
"""
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .enums import EquipmentStatus, EquipmentType, JobPriority, JobStatus, Role


def pg_enum(enum_cls, name: str) -> SAEnum:
    """Store the enum's *value* ("In-Use") rather than its name ("IN_USE")."""
    return SAEnum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(pg_enum(Role, "user_role"))
    job_title: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(default=True)
    # Home farm - used for the co-location question.
    farm_id: Mapped[int | None] = mapped_column(ForeignKey("farms.id", ondelete="SET NULL"))
    # Reporting line - a farmhand reports to a Regional Agronomy Supervisor.
    supervisor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    farm: Mapped["Farm | None"] = relationship(foreign_keys=[farm_id], back_populates="staff")
    supervisor: Mapped["User | None"] = relationship(
        remote_side=[id], back_populates="direct_reports"
    )
    direct_reports: Mapped[list["User"]] = relationship(back_populates="supervisor")

    # Read-only helpers so Pydantic can serialise flat names for the UI grids.
    @property
    def farm_name(self) -> str | None:
        return self.farm.name if self.farm else None

    @property
    def supervisor_name(self) -> str | None:
        return self.supervisor.full_name if self.supervisor else None


class Farm(TimestampMixin, Base):
    __tablename__ = "farms"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    location_region: Mapped[str] = mapped_column(String(80), index=True)
    capacity: Mapped[int] = mapped_column(Integer)
    # farms -> users and users -> farms reference each other; use_alter adds
    # this foreign key after both tables exist, breaking the creation cycle.
    supervisor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True, name="fk_farms_supervisor")
    )

    supervisor: Mapped["User | None"] = relationship(foreign_keys=[supervisor_id])
    staff: Mapped[list["User"]] = relationship(foreign_keys=[User.farm_id], back_populates="farm")
    equipment: Mapped[list["Equipment"]] = relationship(back_populates="farm")

    @property
    def supervisor_name(self) -> str | None:
        return self.supervisor.full_name if self.supervisor else None

    @property
    def equipment_count(self) -> int:
        return len(self.equipment)


class Equipment(TimestampMixin, Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    serial_number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    model: Mapped[str] = mapped_column(String(80), index=True)
    equipment_type: Mapped[EquipmentType] = mapped_column(pg_enum(EquipmentType, "equipment_type"))
    status: Mapped[EquipmentStatus] = mapped_column(
        pg_enum(EquipmentStatus, "equipment_status"), default=EquipmentStatus.IDLE, index=True
    )
    fuel_level: Mapped[float] = mapped_column(Float)  # percent, 0-100
    facility_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="RESTRICT"), index=True)
    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    last_service_date: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    farm: Mapped["Farm"] = relationship(back_populates="equipment")
    assigned_to: Mapped["User | None"] = relationship()
    field_jobs: Mapped[list["FieldJob"]] = relationship(back_populates="equipment")

    @property
    def farm_name(self) -> str | None:
        return self.farm.name if self.farm else None

    @property
    def assigned_to_name(self) -> str | None:
        return self.assigned_to.full_name if self.assigned_to else None


class FieldJob(TimestampMixin, Base):
    __tablename__ = "field_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    priority: Mapped[JobPriority] = mapped_column(pg_enum(JobPriority, "job_priority"))
    status: Mapped[JobStatus] = mapped_column(
        pg_enum(JobStatus, "job_status"), default=JobStatus.PENDING, index=True
    )
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id", ondelete="CASCADE"), index=True)
    operator_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    scheduled_date: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    equipment: Mapped["Equipment"] = relationship(back_populates="field_jobs")
    operator: Mapped["User | None"] = relationship()
    service_reports: Mapped[list["ServiceReport"]] = relationship(
        back_populates="field_job", cascade="all, delete-orphan"
    )

    @property
    def equipment_serial(self) -> str | None:
        return self.equipment.serial_number if self.equipment else None

    @property
    def equipment_model(self) -> str | None:
        return self.equipment.model if self.equipment else None

    @property
    def farm_name(self) -> str | None:
        return self.equipment.farm.name if self.equipment and self.equipment.farm else None

    @property
    def operator_name(self) -> str | None:
        return self.operator.full_name if self.operator else None

    @property
    def report_count(self) -> int:
        return len(self.service_reports)


class ServiceReport(TimestampMixin, Base):
    __tablename__ = "service_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    field_job_id: Mapped[int] = mapped_column(
        ForeignKey("field_jobs.id", ondelete="CASCADE"), index=True
    )
    file_url: Mapped[str] = mapped_column(String(512))  # s3://bucket/key
    file_key: Mapped[str] = mapped_column(String(400))  # key inside the bucket
    file_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    field_job: Mapped["FieldJob"] = relationship(back_populates="service_reports")
    uploaded_by: Mapped["User | None"] = relationship()

    @property
    def uploaded_by_name(self) -> str | None:
        return self.uploaded_by.full_name if self.uploaded_by else None


class AuditLog(TimestampMixin, Base):
    """Append-only record of who changed what - searchable by auditors."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    user_email: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(40), index=True)  # CREATE, UPDATE, LOGIN...
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[str | None] = mapped_column(Text)
