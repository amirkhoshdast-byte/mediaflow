from datetime import UTC, datetime, timedelta

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.config import get_settings
from app.db import get_db
from app.deps import SESSION_COOKIE, current_user, is_locked
from app.enums import Role
from app.models import User
from app.permissions import PERMISSIONS
from app.security import decrypt_secret, encrypt_secret, make_token, read_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

CHALLENGE_MINUTES = 10


class LoginIn(BaseModel):
    username: str
    password: str


class TotpIn(BaseModel):
    challenge_token: str
    code: str


class EnrollIn(BaseModel):
    challenge_token: str


class EnrollConfirmIn(BaseModel):
    challenge_token: str
    code: str


def _fail(db: Session, user: User) -> None:
    s = get_settings()
    user.failed_attempts += 1
    if user.failed_attempts >= s.max_failed_attempts:
        user.locked_until = datetime.now(UTC) + timedelta(minutes=s.lock_minutes)
        user.failed_attempts = 0
        audit.log(db, user.id, "auth.locked", "user", user.id)
    audit.log(db, user.id, "auth.failed", "user", user.id)
    db.commit()


def _start_session(response: Response, db: Session, user: User) -> dict:
    s = get_settings()
    user.failed_attempts = 0
    user.locked_until = None
    audit.log(db, user.id, "auth.login", "user", user.id)
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        make_token(user.id, "session", s.session_hours * 60),
        max_age=s.session_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=s.cookie_secure,
        path="/",
    )
    return serialize_user(user)


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "ui_language": user.ui_language,
        "permissions": sorted(p.value for p in PERMISSIONS[Role(user.role)]),
    }


def _user_from_challenge(db: Session, token: str, purpose: str) -> User:
    user_id = read_token(token, purpose)
    user = db.get(User, user_id) if user_id else None
    if not user or not user.is_active:
        raise HTTPException(401, "invalid_challenge")
    if is_locked(user):
        raise HTTPException(423, "account_locked")
    return user


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.username == body.username))
    if not user or not user.is_active:
        raise HTTPException(401, "invalid_credentials")
    if is_locked(user):
        raise HTTPException(423, "account_locked")
    if not verify_password(user.password_hash, body.password):
        _fail(db, user)
        raise HTTPException(401, "invalid_credentials")
    # Password alone never opens a session: a 2FA step always follows.
    if user.totp_enabled:
        return {
            "status": "totp_required",
            "challenge_token": make_token(user.id, "totp", CHALLENGE_MINUTES),
        }
    return {
        "status": "enroll_required",
        "challenge_token": make_token(user.id, "enroll", CHALLENGE_MINUTES),
    }


@router.post("/totp")
def totp(body: TotpIn, response: Response, db: Session = Depends(get_db)) -> dict:
    user = _user_from_challenge(db, body.challenge_token, "totp")
    if not user.totp_enabled or not user.totp_secret_enc:
        raise HTTPException(401, "invalid_challenge")
    if not pyotp.TOTP(decrypt_secret(user.totp_secret_enc)).verify(body.code, valid_window=1):
        _fail(db, user)
        raise HTTPException(401, "invalid_code")
    return _start_session(response, db, user)


@router.post("/enroll/start")
def enroll_start(body: EnrollIn, db: Session = Depends(get_db)) -> dict:
    user = _user_from_challenge(db, body.challenge_token, "enroll")
    if user.totp_enabled:
        raise HTTPException(409, "already_enrolled")
    secret = pyotp.random_base32()
    user.totp_secret_enc = encrypt_secret(secret)
    db.commit()
    uri = pyotp.TOTP(secret).provisioning_uri(
        name=user.username, issuer_name="Narrative Command Room"
    )
    return {"secret": secret, "otpauth_uri": uri}


@router.post("/enroll/confirm")
def enroll_confirm(
    body: EnrollConfirmIn, response: Response, db: Session = Depends(get_db)
) -> dict:
    user = _user_from_challenge(db, body.challenge_token, "enroll")
    if user.totp_enabled or not user.totp_secret_enc:
        raise HTTPException(409, "enroll_not_started")
    if not pyotp.TOTP(decrypt_secret(user.totp_secret_enc)).verify(body.code, valid_window=1):
        _fail(db, user)
        raise HTTPException(401, "invalid_code")
    user.totp_enabled = True
    audit.log(db, user.id, "auth.2fa_enrolled", "user", user.id)
    return _start_session(response, db, user)


@router.post("/logout")
def logout(
    response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    audit.log(db, user.id, "auth.logout", "user", user.id)
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return serialize_user(user)
