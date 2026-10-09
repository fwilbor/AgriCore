from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import or_, select, true
from sqlalchemy.orm import Session, selectinload

from .. import audit
from ..deps import AdminUser, CurrentUser, DbSession
from ..enums import EquipmentStatus, EquipmentType, Role
from ..models import Equipment, Farm, FieldJob, User
from ..schemas import EquipmentCreate, EquipmentOut, EquipmentUpdate
from ..utils import apply_updates, describe, get_or_404

router = APIRouter(prefix="/equipment", tags=["equipment"])


def visible_to(user: User):
    """WHERE clause limiting which equipment rows a user may see.

    Farm Hands see only units assigned to them or used on one of their jobs;
    admins and auditors see everything (no extra filter).
    """
    if user.role != Role.FARM_HAND:
        return true()
    their_job_equipment = select(FieldJob.equipment_id).where(FieldJob.operator_id == user.id)
    return or_(Equipment.assigned_to_id == user.id, Equipment.id.in_(their_job_equipment))


def validate_references(db: Session, facility_id: int | None, assigned_to_id: int | None):
    """Pydantic checks shape; this checks that referenced rows really exist."""
    if facility_id is not None and db.get(Farm, facility_id) is None:
        raise HTTPException(422, f"Farm {facility_id} does not exist")
    if assigned_to_id is not None:
        hand = db.get(User, assigned_to_id)
        if hand is None or hand.role != Role.FARM_HAND:
            raise HTTPException(
                422, f"User {assigned_to_id} is not a farm hand"
            )


@router.get("", response_model=list[EquipmentOut])
def list_equipment(
    db: DbSession,
    user: CurrentUser,
    status_filter: EquipmentStatus | None = Query(None, alias="status"),
    equipment_type: EquipmentType | None = None,
    facility_id: int | None = None,
    search: str | None = None,
):
    stmt = (
        select(Equipment)
        .options(selectinload(Equipment.farm), selectinload(Equipment.assigned_to))
        .where(visible_to(user))
        .order_by(Equipment.serial_number)
    )
    if status_filter:
        stmt = stmt.where(Equipment.status == status_filter)
    if equipment_type:
        stmt = stmt.where(Equipment.equipment_type == equipment_type)
    if facility_id:
        stmt = stmt.where(Equipment.facility_id == facility_id)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Equipment.serial_number.ilike(like), Equipment.model.ilike(like)))
    return db.scalars(stmt).all()


@router.get("/{equipment_id}", response_model=EquipmentOut)
def get_equipment(equipment_id: int, db: DbSession, user: CurrentUser):
    item = db.scalar(select(Equipment).where(Equipment.id == equipment_id, visible_to(user)))
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Equipment {equipment_id} not found")
    return item


@router.post("", response_model=EquipmentOut, status_code=status.HTTP_201_CREATED)
def create_equipment(payload: EquipmentCreate, db: DbSession, admin: AdminUser):
    validate_references(db, payload.facility_id, payload.assigned_to_id)
    if db.scalar(select(Equipment).where(Equipment.serial_number == payload.serial_number)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Serial number already exists")
    item = Equipment(**payload.model_dump())
    db.add(item)
    db.flush()
    audit.record(db, admin, "CREATE", "equipment", item.id, f"{item.serial_number} {item.model}")
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{equipment_id}", response_model=EquipmentOut)
def update_equipment(equipment_id: int, payload: EquipmentUpdate, db: DbSession, admin: AdminUser):
    item = get_or_404(db, Equipment, equipment_id)
    validate_references(db, payload.facility_id, payload.assigned_to_id)
    changes = apply_updates(item, payload)
    audit.record(db, admin, "UPDATE", "equipment", item.id, f"{item.serial_number}: {describe(changes)}")
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{equipment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_equipment(equipment_id: int, db: DbSession, admin: AdminUser):
    item = get_or_404(db, Equipment, equipment_id)
    if item.field_jobs:
        # Deleting would erase job history that the reliability metrics rely on.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Equipment has field job history - set its status to Retired instead",
        )
    audit.record(db, admin, "DELETE", "equipment", item.id, item.serial_number)
    db.delete(item)
    db.commit()
