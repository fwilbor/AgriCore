"""Shared pytest fixtures.

* Points the app at the separate agricore_test database (never your demo data).
* Replaces S3 with moto's in-process mock, so no emulator or AWS account is needed.
* Re-seeds before each test module so every file starts from the same known data.
"""
import os

import pytest
from moto import mock_aws

from app.config import Settings, get_settings

os.environ["DATABASE_URL"] = Settings().test_database_url
os.environ["S3_ENDPOINT_URL"] = ""  # empty -> boto3 talks to "AWS", which moto intercepts
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
get_settings.cache_clear()

PASSWORD = "AgriCore2026!"


@pytest.fixture(scope="session", autouse=True)
def aws():
    with mock_aws():
        yield


@pytest.fixture(scope="module", autouse=True)
def seeded_db(aws):
    from app import seed
    from app.database import Base, SessionLocal, engine
    from app.storage import get_s3_client

    get_s3_client.cache_clear()  # make sure the client is created inside mock_aws
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed.seed(db)


@pytest.fixture(scope="session")
def client(aws):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


def _headers(client, email):
    res = client.post("/api/auth/login", data={"username": email, "password": PASSWORD})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def admin(client):
    return _headers(client, "admin@prairiecrest.coop")


@pytest.fixture
def farm_hand(client):
    return _headers(client, "farmhand@prairiecrest.coop")


@pytest.fixture
def auditor(client):
    return _headers(client, "auditor@prairiecrest.coop")
