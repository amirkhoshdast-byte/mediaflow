from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.db import get_db
from app.deps import current_user, require
from app.enums import RedLineKind, RiskLevel
from app.models import RedLine, User
from app.permissions import Perm

router = APIRouter(prefix="/redlines", tags=["redlines"])


def serialize(r: RedLine) -> dict:
    return {
        "id": r.id,
        "kind": r.kind,
        "pattern": r.pattern,
        "description": r.description,
        "severity": r.severity,
        "active": r.active,
    }


class RedLineIn(BaseModel):
    kind: RedLineKind
    pattern: str = Field(min_length=2, max_length=300)
    description: str | None = Field(default=None, max_length=500)
    severity: RiskLevel = RiskLevel.HIGH


class RedLinePatch(BaseModel):
    pattern: str | None = Field(default=None, min_length=2, max_length=300)
    description: str | None = Field(default=None, max_length=500)
    severity: RiskLevel | None = None
    active: bool | None = None


def _get(db: Session, red_line_id: str) -> RedLine:
    r = db.get(RedLine, red_line_id)
    if not r:
        raise HTTPException(404, "red_line_not_found")
    return r


@router.get("")
def list_red_lines(_: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(RedLine).order_by(RedLine.kind.desc(), RedLine.created_at))
    return [serialize(r) for r in rows]


@router.post("", status_code=201)
def create_red_line(
    body: RedLineIn,
    user: User = Depends(require(Perm.REDLINE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    pattern = body.pattern.strip()
    if db.scalar(
        select(RedLine.id).where(RedLine.kind == body.kind.value, RedLine.pattern == pattern)
    ):
        raise HTTPException(409, "red_line_exists")
    r = RedLine(
        kind=body.kind.value,
        pattern=pattern,
        description=body.description,
        severity=body.severity.value,
        created_by=user.id,
    )
    db.add(r)
    db.flush()
    audit.log(db, user.id, "redline.created", "red_line", r.id, serialize(r))
    db.commit()
    return serialize(r)


@router.patch("/{red_line_id}")
def update_red_line(
    red_line_id: str,
    body: RedLinePatch,
    user: User = Depends(require(Perm.REDLINE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    r = _get(db, red_line_id)
    before = serialize(r)
    changes = body.model_dump(exclude_unset=True)
    if "pattern" in changes:
        changes["pattern"] = changes["pattern"].strip()
    if "severity" in changes and changes["severity"] is not None:
        changes["severity"] = changes["severity"].value
    for key, value in changes.items():
        if value is not None or key == "description":
            setattr(r, key, value)
    audit.log(
        db, user.id, "redline.updated", "red_line", r.id, {"before": before, "after": serialize(r)}
    )
    db.commit()
    return serialize(r)


@router.delete("/{red_line_id}", status_code=204)
def delete_red_line(
    red_line_id: str,
    user: User = Depends(require(Perm.REDLINE_MANAGE)),
    db: Session = Depends(get_db),
) -> None:
    r = _get(db, red_line_id)
    audit.log(db, user.id, "redline.deleted", "red_line", r.id, serialize(r))
    db.delete(r)
    db.commit()
