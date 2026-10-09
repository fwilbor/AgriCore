"""FastAPI application entry point.

Run locally:   uvicorn app.main:app --reload     (from backend/)
On AWS Lambda: the `handler` at the bottom wraps the same app with Mangum.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from . import models  # noqa: F401  (registers every table on Base.metadata)
from . import storage
from .config import get_settings
from .database import Base, engine
from .routers import analytics, audit_logs, auth, equipment, farms, jobs, reports, users

log = logging.getLogger("agricore")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once at startup (before `yield`) and once at shutdown (after)."""
    Base.metadata.create_all(bind=engine)  # no-op if the tables already exist
    if get_settings().s3_endpoint_url:  # local emulator only; on AWS the deploy script creates the bucket
        try:
            storage.ensure_bucket()
        except Exception as exc:  # the API still works for everything except uploads
            log.warning("S3 not reachable (%s) - service report uploads will fail", exc)
    yield


app = FastAPI(
    title="AgriCore API",
    description="**Equipment. Service. Insight.** Prairie Crest Agricultural Cooperative - Smart Farm Command Center",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS lets a browser page on another origin (e.g. CloudFront) call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api")
for module in (auth, users, farms, equipment, jobs, reports, analytics, audit_logs):
    api.include_router(module.router)


@api.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


app.include_router(api)

# AWS Lambda entry point (unused locally). lifespan="off" because Mangum would
# otherwise rerun the startup code on *every* request; on AWS the tables are
# created by bin/seed.sh and the bucket by bin/aws/2-storage.sh.
handler = Mangum(app, lifespan="off")
