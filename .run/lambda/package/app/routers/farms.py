from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .. import audit
from ..deps import AdminUser, CurrentUser, DbSession
from ..models import Farm
from ..schemas import FarmCreate, FarmOut, FarmUpdate
from ..utils import apply_updates, describe, get_or_404

router = APIRouter(prefix="/farms", tags=["farms"])


@router.get("", response_model=list[FarmOut])
def list_farms(db: DbSession, _: CurrentUser):
    stmt = (
        select(Farm)
        .options(selectinload(Farm.supervisor), selectinload(Farm.equipment))
        .order_by(Farm.name)
    )
    return db.scalars(stmt).all()


@router.get("/{farm_id}", response_model=FarmOut)
def get_farm(farm_id: int, db: DbSession, _: CurrentUser):
    return get_or_404(db, Farm, farm_id)


@router.post("", response_model=FarmOut, status_code=status.HTTP_201_CREATED)
def create_farm(payload: FarmCreate, db: DbSession, admin: AdminUser):
    farm = Farm(**payload.model_dump())
    db.add(farm)
    db.flush()
    audit.record(db, admin, "CREATE", "farm", farm.id, farm.name)
    db.commit()
    db.refresh(farm)
    return farm


@router.patch("/{farm_id}", response_model=FarmOut)
def update_farm(farm_id: int, payload: FarmUpdate, db: DbSession, admin: AdminUser):
    farm = get_or_404(db, Farm, farm_id)
    changes = apply_updates(farm, payload)
    audit.record(db, admin, "UPDATE", "farm", farm.id, describe(changes))
    db.commit()
    db.refresh(farm)
    return farm


@router.delete("/{farm_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_farm(farm_id: int, db: DbSession, admin: AdminUser):
    farm = get_or_404(db, Farm, farm_id)
    if farm.equipment:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{farm.name} still houses {len(farm.equipment)} equipment units; move them first",
        )
    audit.record(db, admin, "DELETE", "farm", farm.id, farm.name)
    db.delete(farm)
    db.commit()
