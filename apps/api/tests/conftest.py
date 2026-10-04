import os

import psycopg
import pytest
from sqlalchemy.engine import make_url

BASE_URL = os.environ["DATABASE_URL"]
TEST_DB = "ncr_test"
_url = make_url(BASE_URL)
os.environ["DATABASE_URL"] = _url.set(database=TEST_DB).render_as_string(hide_password=False)
os.environ.setdefault("SECRET_KEY", "test-secret-key-test-secret-key-test")

with psycopg.connect(
    _url.set(drivername="postgresql").render_as_string(hide_password=False), autocommit=True
) as conn:
    if not conn.execute("select 1 from pg_database where datname=%s", (TEST_DB,)).fetchone():
        conn.execute(f"create database {TEST_DB}")

import pyotp  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402,F401
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.enums import Role  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.security import encrypt_secret, hash_password  # noqa: E402

PASSWORD = "test-password-123"


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    with TestClient(app, headers={"x-ncr": "1"}) as c:
        yield c


@pytest.fixture
def make_user():
    """Create a user with 2FA already enrolled; returns (user_id, totp_secret)."""

    def _make(username: str, role: Role, enrolled: bool = True):
        secret = pyotp.random_base32()
        with SessionLocal() as db:
            u = User(
                username=username,
                display_name=username,
                password_hash=hash_password(PASSWORD),
                role=role.value,
                totp_enabled=enrolled,
                totp_secret_enc=encrypt_secret(secret) if enrolled else None,
            )
            db.add(u)
            db.commit()
            return u.id, secret

    return _make


@pytest.fixture
def login(client, make_user):
    """Log in as a fresh user of the given role; returns a client with a session cookie."""

    def _login(role: Role, username: str | None = None) -> TestClient:
        username = username or f"u_{role.value}"
        _, secret = make_user(username, role)
        r = client.post("/auth/login", json={"username": username, "password": PASSWORD})
        r = client.post(
            "/auth/totp",
            json={"challenge_token": r.json()["challenge_token"], "code": pyotp.TOTP(secret).now()},
        )
        assert r.status_code == 200, r.text
        return client

    return _login
