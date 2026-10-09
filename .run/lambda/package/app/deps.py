"""FastAPI dependencies - the heart of authentication and RBAC.

`Depends(x)` tells FastAPI: "before running this endpoint, call x() and pass
me its result." Dependencies can depend on other dependencies, forming a chain:

    endpoint -> require_roles(...) -> get_current_user -> oauth2_scheme + get_db

If any link raises HTTPException, the endpoint never runs.
"""
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .database import get_db
from .enums import Role
from .models import User
from .security import decode_access_token

# Reads the "Authorization: Bearer <token>" header. tokenUrl powers the
# "Authorize" button in the Swagger docs at /docs.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# `Annotated` aliases keep endpoint signatures short and readable.
DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DbSession) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise unauthorized
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed: Role):
    """Dependency *factory*: builds a dependency that only lets `allowed` roles through.

    401 = "I don't know who you are"   (handled by get_current_user)
    403 = "I know who you are, but you're not allowed"   (handled here)
    """

    def checker(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role.value}' cannot perform this action",
            )
        return user

    return checker


AdminUser = Annotated[User, Depends(require_roles(Role.ADMIN))]
AdminOrAuditor = Annotated[User, Depends(require_roles(Role.ADMIN, Role.AUDITOR))]
AdminOrFarmHand = Annotated[User, Depends(require_roles(Role.ADMIN, Role.FARM_HAND))]
