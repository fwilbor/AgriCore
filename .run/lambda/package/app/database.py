"""SQLAlchemy 2.0 engine, session factory and the `get_db` dependency."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

# The engine owns the connection pool. pool_pre_ping checks a connection is
# alive before handing it out (important for RDS, which drops idle connections).
engine = create_engine(get_settings().database_url, pool_pre_ping=True)

# A factory that produces new Session objects bound to the engine.
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Every ORM model inherits from this; Base.metadata knows all tables."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one Session per request, always closed afterwards.

    `yield` hands the session to the endpoint; the `finally` block runs after
    the response is produced, even if the endpoint raised an exception.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
