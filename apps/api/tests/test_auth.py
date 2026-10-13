import pyotp

from app.enums import Role
from tests.conftest import PASSWORD


def test_password_alone_never_opens_a_session(client, make_user):
    make_user("amir", Role.ASSISTANT)
    r = client.post("/auth/login", json={"username": "amir", "password": PASSWORD})
    assert r.json()["status"] == "totp_required"
    assert "ncr_session" not in client.cookies
    assert client.get("/auth/me").status_code == 401


def test_totp_login_sets_session(client, make_user):
    _, secret = make_user("amir", Role.ASSISTANT)
    tok = client.post("/auth/login", json={"username": "amir", "password": PASSWORD}).json()
    r = client.post(
        "/auth/totp",
        json={"challenge_token": tok["challenge_token"], "code": pyotp.TOTP(secret).now()},
    )
    assert r.status_code == 200
    me = client.get("/auth/me").json()
    assert me["role"] == "assistant"
    assert "draft:edit" in me["permissions"] and "draft:approve" not in me["permissions"]


def test_wrong_totp_rejected(client, make_user):
    make_user("amir", Role.ASSISTANT)
    tok = client.post("/auth/login", json={"username": "amir", "password": PASSWORD}).json()
    r = client.post(
        "/auth/totp", json={"challenge_token": tok["challenge_token"], "code": "000000"}
    )
    assert r.status_code == 401
    assert client.get("/auth/me").status_code == 401


def test_first_login_requires_enrollment(client, make_user):
    make_user("new", Role.ASSISTANT, enrolled=False)
    tok = client.post("/auth/login", json={"username": "new", "password": PASSWORD}).json()
    assert tok["status"] == "enroll_required"
    # Enrollment token cannot be used as a TOTP challenge
    r = client.post(
        "/auth/totp", json={"challenge_token": tok["challenge_token"], "code": "123456"}
    )
    assert r.status_code == 401
    start = client.post(
        "/auth/enroll/start", json={"challenge_token": tok["challenge_token"]}
    ).json()
    r = client.post(
        "/auth/enroll/confirm",
        json={
            "challenge_token": tok["challenge_token"],
            "code": pyotp.TOTP(start["secret"]).now(),
        },
    )
    assert r.status_code == 200
    assert client.get("/auth/me").status_code == 200


def test_lock_after_five_failures(client, make_user):
    make_user("amir", Role.ASSISTANT)
    for _ in range(5):
        assert (
            client.post("/auth/login", json={"username": "amir", "password": "bad"}).status_code
            == 401
        )
    r = client.post("/auth/login", json={"username": "amir", "password": PASSWORD})
    assert r.status_code == 423


def test_csrf_header_required(make_user):
    from fastapi.testclient import TestClient

    from app.main import app

    make_user("amir", Role.ASSISTANT)
    with TestClient(app) as bare:
        r = bare.post("/auth/login", json={"username": "amir", "password": PASSWORD})
        assert r.status_code == 403


def test_admin_endpoints_only_for_sysadmin(login):
    c = login(Role.ASSISTANT)
    assert c.get("/admin/users").status_code == 403
    assert c.post("/admin/users", json={}).status_code == 403


def test_sysadmin_creates_user_and_audit_logged(login):
    c = login(Role.SYSADMIN)
    r = c.post(
        "/admin/users",
        json={
            "username": "editor1",
            "display_name": "E",
            "password": "long-enough-pass",
            "role": "assistant",
        },
    )
    assert r.status_code == 201
    actions = [a["action"] for a in c.get("/admin/audit").json()]
    assert "user.created" in actions and "auth.login" in actions
