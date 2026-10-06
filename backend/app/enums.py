"""Enumerations shared by the database models and the Pydantic schemas.

Subclassing `str` means each member *is* a string ("In-Use"), so it
serialises to JSON cleanly and compares equal to plain strings.
"""
from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"            # Farm Operations Admin - full CRUD
    FARM_HAND = "farm_hand"    # assigned equipment, job status, service reports
    AUDITOR = "auditor"        # read-only: dashboards, grids, audit log


class EquipmentType(str, Enum):
    TRACTOR = "Tractor"
    COMBINE = "Combine"
    SPRAYER = "Sprayer"
    IRRIGATION_PUMP = "Irrigation Pump"


class EquipmentStatus(str, Enum):
    IDLE = "Idle"
    IN_USE = "In-Use"
    MAINTENANCE = "Maintenance"
    RETIRED = "Retired"


class JobPriority(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    CRITICAL = "Critical"


class JobStatus(str, Enum):
    PENDING = "Pending"
    IN_PROGRESS = "In-Progress"
    COMPLETED = "Completed"
    FAILED = "Failed"


# "Active" equipment = currently available or working (not in the shop, not retired).
ACTIVE_EQUIPMENT_STATUSES = (EquipmentStatus.IDLE, EquipmentStatus.IN_USE)
# "Active" field jobs = not yet finished.
ACTIVE_JOB_STATUSES = (JobStatus.PENDING, JobStatus.IN_PROGRESS)
FINISHED_JOB_STATUSES = (JobStatus.COMPLETED, JobStatus.FAILED)
