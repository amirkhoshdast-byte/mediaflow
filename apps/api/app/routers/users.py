from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.db import get_db
from app.deps import require
from app.enums import Role
from app.models import AuditLog, User
from app.permissions import Perm
from app.security import hash_password

router = APIRouter(prefix="/admin", tags=["admin"])


class UserIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=10)
    role: Role


class UserPatch(BaseModel):
    role: Role | None = None
    is_active: bool | None = None
    reset_2fa: bool = False


def _out(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "display_name": u.display_name,
        "role": u.role,
        "is_active": u.is_active,
        "totp_enabled": u.totp_enabled,
    }


@router.get("/users")
def list_users(
    _: User = Depends(require(Perm.USERS_MANAGE)), db: Session = Depends(get_db)
) -> list[dict]:
    return [_out(u) for u in db.scalars(select(User).order_by(User.created_at))]


@router.post("/users", status_code=201)
def create_user(
    body: UserIn, actor: User = Depends(require(Perm.USERS_MANAGE)), db: Session = Depends(get_db)
) -> dict:
    if db.scalar(select(User).where(User.username == body.username)):
        raise HTTPException(409, "username_taken")
    user = User(
        username=body.username,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
        role=body.role.value,
    )
    db.add(user)
    db.flush()
    audit.log(db, actor.id, "user.created", "user", user.id, {"role": user.role})
    db.commit()
    return _out(user)


@router.patch("/users/{user_id}")
def patch_user(
    user_id: str,
    body: UserPatch,
    actor: User = Depends(require(Perm.USERS_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "not_found")
    if body.role and body.role.value != user.role:
        audit.log(
            db,
            actor.id,
            "user.role_changed",
            "user",
            user.id,
            {"from": user.role, "to": body.role.value},
        )
        user.role = body.role.value
    if body.is_active is not None:
        user.is_active = body.is_active
        audit.log(db, actor.id, "user.active_changed", "user", user.id, {"active": body.is_active})
    if body.reset_2fa:
        user.totp_enabled = False
        user.totp_secret_enc = None
        audit.log(db, actor.id, "user.2fa_reset", "user", user.id)
    db.commit()
    return _out(user)


@router.get("/audit")
def audit_log(
    limit: int = 100, _: User = Depends(require(Perm.AUDIT_VIEW)), db: Session = Depends(get_db)
) -> list[dict]:
    rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(limit, 500)))
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "action": r.action,
            "entity": r.entity,
            "entity_id": r.entity_id,
            "detail": r.detail,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
