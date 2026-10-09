"""Small helpers shared by the routers."""
from typing import TypeVar

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

T = TypeVar("T")


def get_or_404(db: Session, model: type[T], obj_id: int) -> T:
    obj = db.get(model, obj_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{model.__name__} {obj_id} not found")
    return obj


def apply_updates(obj, payload: BaseModel) -> dict:
    """Copy only the fields the client actually sent (PATCH semantics).

    exclude_unset=True is the key: a field the client omitted is left alone,
    while a field explicitly sent as null *is* applied.
    """
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(obj, field, value)
    return changes


def describe(changes: dict) -> str:
    """Human-readable change summary for the audit log."""
    return ", ".join(f"{k}={getattr(v, 'value', v)}" for k, v in changes.items())
