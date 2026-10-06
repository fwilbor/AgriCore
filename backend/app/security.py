"""Password hashing (bcrypt) and JWT creation/verification (PyJWT)."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import get_settings
from .models import User


def hash_password(password: str) -> str:
    # bcrypt salts automatically and is deliberately slow to resist brute force.
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(user: User) -> str:
    """A JWT is a signed JSON payload. Anyone can *read* it, but only the
    server (holding JWT_SECRET) can *create* a valid signature, so the client
    can't tamper with the user id or role inside."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),  # subject = who this token belongs to
        "role": user.role.value,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError if the signature is bad or the token expired."""
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
