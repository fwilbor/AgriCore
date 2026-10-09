"""Application settings.

pydantic-settings reads values from environment variables first, then from
backend/.env. Every setting has a type, so a bad value (e.g. a non-numeric
token lifetime) fails loudly at startup instead of deep inside a request.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    # Database
    database_url: str = "postgresql+psycopg://agricore:agricore@localhost:5432/agricore"
    test_database_url: str = "postgresql+psycopg://agricore:agricore@localhost:5432/agricore_test"

    # Auth
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    # CORS
    cors_origins: list[str] = ["http://localhost:5173"]

    # S3 storage
    s3_bucket: str = "agricore-service-reports"
    s3_endpoint_url: str | None = None  # set to the moto emulator locally
    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    max_upload_mb: int = 10
    presigned_url_seconds: int = 300


@lru_cache
def get_settings() -> Settings:
    """Cached so .env is parsed once per process."""
    return Settings()
