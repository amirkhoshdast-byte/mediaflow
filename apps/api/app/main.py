import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.config import get_settings
from app.db import SessionLocal
from app.enums import Role
from app.models import User
from app.routers import auth, users
from app.security import hash_password

log = logging.getLogger("ncr")


def bootstrap_admin() -> None:
    s = get_settings()
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(User)):
            return
        if not s.bootstrap_admin_password:
            log.warning("No users exist and BOOTSTRAP_ADMIN_PASSWORD is empty; no admin created.")
            return
        db.add(
            User(
                username=s.bootstrap_admin_username,
                display_name="مدیر سامانه",
                password_hash=hash_password(s.bootstrap_admin_password),
                role=Role.SYSADMIN.value,
            )
        )
        db.commit()
        log.warning("Bootstrap admin '%s' created.", s.bootstrap_admin_username)


@asynccontextmanager
async def lifespan(_: FastAPI):
    bootstrap_admin()
    yield


app = FastAPI(title="Narrative Command Room", root_path="/api", lifespan=lifespan)


@app.middleware("http")
async def csrf_guard(request: Request, call_next):
    # Cookie sessions are SameSite=Lax; additionally every state-changing call must carry
    # a custom header that a cross-site form post cannot set.
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.headers.get("x-ncr") != "1":
        return JSONResponse({"detail": "csrf"}, status_code=403)
    return await call_next(request)


app.include_router(auth.router)
app.include_router(users.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
