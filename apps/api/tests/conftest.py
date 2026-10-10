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
from sqlalchemy import select  # noqa: E402

from app import models  # noqa: E402,F401
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.enums import Role  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.security import decrypt_secret, encrypt_secret, hash_password  # noqa: E402

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
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.username == username))
        if user:  # re-login as an existing user: reuse its TOTP secret
            secret = decrypt_secret(user.totp_secret_enc)
        else:
            _, secret = make_user(username, role)
        client.cookies.clear()
        r = client.post("/auth/login", json={"username": username, "password": PASSWORD})
        r = client.post(
            "/auth/totp",
            json={"challenge_token": r.json()["challenge_token"], "code": pyotp.TOTP(secret).now()},
        )
        assert r.status_code == 200, r.text
        return client

    return _login


# ---------- AI fakes ----------
import json  # noqa: E402

from app.ai import gateway as gw  # noqa: E402
from app.ai.providers import Provider  # noqa: E402
from app.celery_app import celery  # noqa: E402

celery.conf.task_always_eager = True


class FakeProvider(Provider):
    def __init__(self, name: str, is_local: bool):
        self.name, self.is_local = name, is_local
        self.calls: list[tuple[str, str]] = []
        self.embed_calls: list[list[str]] = []
        self.analysis = {
            "title": "عنوان آزمون",
            "summary": "خلاصه آزمون.",
            "category": "diplomacy",
            "region": "اروپا",
            "risk": "low",
            "approach": "original_post",
            "opportunity": "فرصت",
            "sentiment": 0.2,
        }

    def embed(self, texts):
        self.embed_calls.append(texts)
        return [[0.0, 1.0] for _ in texts]

    def complete(self, system, user, *, model, max_tokens):
        self.calls.append((system, user))
        if "Analyse this item" in user:
            return "```json\n" + json.dumps(self.analysis) + "\n```"
        return json.dumps(
            {
                "variants": [
                    {"angle": f"زاویه {i}", "parts": [f"متن شماره {i} #تست"]} for i in range(1, 4)
                ]
            }
        )


@pytest.fixture(autouse=True)
def fake_ai(monkeypatch):
    providers = {
        "ollama": FakeProvider("ollama", True),
        "anthropic": FakeProvider("anthropic", False),
    }
    monkeypatch.setattr(gw, "_gateway", gw.AIGateway(providers=providers))
    return providers
