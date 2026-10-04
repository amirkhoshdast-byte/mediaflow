from datetime import UTC, datetime

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.permissions import Perm, has_perm
from app.security import read_token

SESSION_COOKIE = "ncr_session"


def current_user(
    session: str | None = Cookie(default=None, alias=SESSION_COOKIE), db: Session = Depends(get_db)
) -> User:
    user_id = read_token(session, "session") if session else None
    user = db.get(User, user_id) if user_id else None
    if not user or not user.is_active:
        raise HTTPException(401, "not_authenticated")
    return user


def require(perm: Perm):
    def dep(user: User = Depends(current_user)) -> User:
        if not has_perm(user.role, perm):
            raise HTTPException(403, "forbidden")
        return user

    return dep


def is_locked(user: User) -> bool:
    return bool(user.locked_until and user.locked_until > datetime.now(UTC))
