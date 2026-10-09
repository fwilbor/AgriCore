from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .. import audit
from ..deps import AdminOrAuditor, AdminUser, DbSession
from ..enums import Role
from ..models import User
from ..schemas import UserCreate, UserOut, UserUpdate
from ..security import hash_password
from ..utils import describe, get_or_404

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(db: DbSession, _: AdminOrAuditor, role: Role | None = None):
    stmt = (
        select(User)
        .options(selectinload(User.farm), selectinload(User.supervisor))
        .order_by(User.full_name)
    )
    if role:
        stmt = stmt.where(User.role == role)
    return db.scalars(stmt).all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: DbSession, admin: AdminUser):
    if db.scalar(select(User).where(User.email == payload.email.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    data = payload.model_dump(exclude={"password"})
    data["email"] = data["email"].lower()
    user = User(**data, hashed_password=hash_password(payload.password))
    db.add(user)
    db.flush()  # assigns user.id without ending the transaction
    audit.record(db, admin, "CREATE", "user", user.id, f"{user.email} as {user.role.value}")
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, db: DbSession, admin: AdminUser):
    user = get_or_404(db, User, user_id)
    changes = payload.model_dump(exclude_unset=True)
    password = changes.pop("password", None)  # never store the plain password
    for field, value in changes.items():
        setattr(user, field, value)
    if password:
        user.hashed_password = hash_password(password)
        changes["password"] = "(changed)"
    audit.record(db, admin, "UPDATE", "user", user.id, describe(changes))
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(user_id: int, db: DbSession, admin: AdminUser):
    """Soft delete: keeps job history intact, but the user can no longer log in."""
    user = get_or_404(db, User, user_id)
    if user.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot deactivate yourself")
    user.is_active = False
    audit.record(db, admin, "DEACTIVATE", "user", user.id, user.email)
    db.commit()
