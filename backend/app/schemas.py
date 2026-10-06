"""Pydantic v2 schemas - the API's contract.

Pattern used for each entity:
  *Base    fields shared by create + read
  *Create  what a client must send to create a row        (request body)
  *Update  every field optional, for PATCH partial updates (request body)
  *Out     what the API returns                           (response_model)

FastAPI validates incoming JSON against these classes and returns a 422 with
a precise error message when something is wrong - no manual checks needed.
"""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .enums import EquipmentStatus, EquipmentType, JobPriority, JobStatus, Role


class ORMModel(BaseModel):
    """Lets Pydantic read SQLAlchemy objects (attributes) instead of dicts."""

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- Auth / Users
class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    role: Role
    job_title: str | None = Field(default=None, max_length=120)
    farm_id: int | None = None
    supervisor_id: int | None = None


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    role: Role | None = None
    job_title: str | None = None
    farm_id: int | None = None
    supervisor_id: int | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserOut(UserBase, ORMModel):
    id: int
    is_active: bool
    farm_name: str | None = None
    supervisor_name: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ----------------------------------------------------------------------- Farms
class FarmBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    location_region: str = Field(min_length=2, max_length=80)
    capacity: int = Field(gt=0, le=500, description="Max equipment units the site can house")
    supervisor_id: int | None = None


class FarmCreate(FarmBase):
    pass


class FarmUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    location_region: str | None = Field(default=None, min_length=2, max_length=80)
    capacity: int | None = Field(default=None, gt=0, le=500)
    supervisor_id: int | None = None


class FarmOut(FarmBase, ORMModel):
    id: int
    supervisor_name: str | None = None
    equipment_count: int = 0


# ------------------------------------------------------------------- Equipment
SERIAL_PATTERN = r"^[A-Z0-9][A-Z0-9-]{3,39}$"


def _clean_serial(v):
    """Accept 'jd8r-2023-0042 ' from a user and store 'JD8R-2023-0042'."""
    return v.strip().upper() if isinstance(v, str) else v


class EquipmentBase(BaseModel):
    serial_number: str = Field(pattern=SERIAL_PATTERN, examples=["JD8R-2023-0042"])
    model: str = Field(min_length=2, max_length=80)
    equipment_type: EquipmentType
    status: EquipmentStatus = EquipmentStatus.IDLE
    fuel_level: float = Field(ge=0, le=100, description="Percent of tank remaining")
    facility_id: int = Field(description="Farm that houses this unit")
    assigned_to_id: int | None = None
    last_service_date: date | None = None

    # mode="before" runs this *before* the pattern check above.
    @field_validator("serial_number", mode="before")
    @classmethod
    def normalise_serial(cls, v):
        return _clean_serial(v)


class EquipmentCreate(EquipmentBase):
    pass


class EquipmentUpdate(BaseModel):
    serial_number: str | None = Field(default=None, pattern=SERIAL_PATTERN)
    model: str | None = Field(default=None, min_length=2, max_length=80)
    equipment_type: EquipmentType | None = None
    status: EquipmentStatus | None = None
    fuel_level: float | None = Field(default=None, ge=0, le=100)
    facility_id: int | None = None
    assigned_to_id: int | None = None
    last_service_date: date | None = None

    @field_validator("serial_number", mode="before")
    @classmethod
    def normalise_serial(cls, v):
        return _clean_serial(v)


class EquipmentOut(EquipmentBase, ORMModel):
    id: int
    farm_name: str | None = None
    assigned_to_name: str | None = None
    updated_at: datetime | None = None


# ------------------------------------------------------------------ Field jobs
class FieldJobBase(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    priority: JobPriority = JobPriority.MEDIUM
    status: JobStatus = JobStatus.PENDING
    equipment_id: int
    operator_id: int | None = None
    scheduled_date: date | None = None


class FieldJobCreate(FieldJobBase):
    pass


class FieldJobUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=160)
    priority: JobPriority | None = None
    status: JobStatus | None = None
    equipment_id: int | None = None
    operator_id: int | None = None
    scheduled_date: date | None = None


class FieldJobStatusUpdate(BaseModel):
    """The only thing a Farm Hand may change on a job."""

    status: JobStatus


class FieldJobOut(FieldJobBase, ORMModel):
    id: int
    equipment_serial: str | None = None
    equipment_model: str | None = None
    farm_name: str | None = None
    operator_name: str | None = None
    report_count: int = 0
    created_at: datetime
    updated_at: datetime | None = None


# ------------------------------------------------------------- Service reports
class ServiceReportOut(ORMModel):
    id: int
    field_job_id: int
    file_name: str
    file_url: str
    content_type: str
    file_size: int
    notes: str | None
    uploaded_by_name: str | None = None
    created_at: datetime


class DownloadUrlOut(BaseModel):
    url: str
    expires_in: int


# ------------------------------------------------------------------- Audit log
class AuditLogOut(ORMModel):
    id: int
    user_email: str | None
    action: str
    entity_type: str
    entity_id: int | None
    detail: str | None
    created_at: datetime


# ------------------------------------------------------------------- Analytics
class LowFuelItem(BaseModel):
    id: int
    serial_number: str
    model: str
    status: EquipmentStatus
    fuel_level: float
    farm_name: str


class LowFuelOut(BaseModel):
    threshold: float
    count: int
    items: list[LowFuelItem]


class CoLocationItem(BaseModel):
    equipment_id: int
    serial_number: str
    model: str
    equipment_farm: str
    farmhand: str
    farmhand_farm: str | None


class CoLocationOut(BaseModel):
    count: int
    items: list[CoLocationItem]


class ReliabilityItem(BaseModel):
    model: str
    completed: int
    failed: int
    total_finished: int
    completion_rate: float  # 0-1
    failure_rate: float  # 0-1


class MaintenanceFlagItem(BaseModel):
    farm_id: int
    farm_name: str
    total_equipment: int
    in_maintenance: int
    maintenance_pct: float  # 0-1
    flagged: bool


class MaintenanceFlagOut(BaseModel):
    threshold: float
    flagged_count: int
    items: list[MaintenanceFlagItem]


class SupervisorActivityItem(BaseModel):
    supervisor_id: int
    supervisor_name: str
    direct_reports: int
    reports_with_active_jobs: int
    active_jobs: int


class DashboardSummary(BaseModel):
    total_farms: int
    total_equipment: int
    equipment_by_status: dict[str, int]
    jobs_by_status: dict[str, int]
    low_fuel_count: int
    maintenance_flagged_farms: int
    colocation_discrepancies: int
    overall_completion_rate: float
