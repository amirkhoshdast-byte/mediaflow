import hashlib
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.db import get_db
from app.deps import current_user, require
from app.enums import SignalStatus, SourceType
from app.models import RawItem, Signal, User
from app.permissions import Perm
from app.tasks import analyze_signal

router = APIRouter(prefix="/signals", tags=["signals"])


class SignalIn(BaseModel):
    text: str = Field(min_length=20, max_length=20000)
    url: str | None = Field(default=None, max_length=1000)


def serialize_signal(s: Signal) -> dict:
    return {
        "id": s.id,
        "status": s.status,
        "title": s.title,
        "summary": s.summary,
        "category": s.category,
        "region": s.region,
        "risk": s.risk,
        "approach": s.approach,
        "opportunity": s.opportunity,
        "sentiment": s.sentiment,
        "error": s.error,
        "text": s.raw_item.text,
        "url": s.raw_item.url,
        "created_at": s.created_at.isoformat(),
    }


def content_hash(text: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", text.strip().lower()).encode()).hexdigest()


@router.get("")
def list_signals(
    limit: int = 100, _: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[dict]:
    rows = db.scalars(select(Signal).order_by(Signal.created_at.desc()).limit(min(limit, 500)))
    return [serialize_signal(s) for s in rows.unique()]


@router.post("", status_code=201)
def add_signal(
    body: SignalIn, user: User = Depends(require(Perm.SIGNAL_ADD)), db: Session = Depends(get_db)
) -> dict:
    digest = content_hash(body.text)
    existing = db.scalar(select(RawItem).where(RawItem.content_hash == digest))
    if existing:
        sig = db.scalar(select(Signal).where(Signal.raw_item_id == existing.id))
        raise HTTPException(409, {"code": "duplicate", "signal_id": sig.id if sig else None})
    item = RawItem(text=body.text.strip(), url=body.url, content_hash=digest, created_by=user.id)
    db.add(item)
    db.flush()
    signal = Signal(raw_item_id=item.id, status=SignalStatus.ANALYZING.value)
    db.add(signal)
    db.flush()
    audit.log(db, user.id, "signal.added", "signal", signal.id, {"source": SourceType.MANUAL.value})
    db.commit()
    analyze_signal.delay(signal.id)
    db.refresh(signal)
    return serialize_signal(signal)


@router.post("/{signal_id}/retry")
def retry_signal(
    signal_id: str, user: User = Depends(require(Perm.SIGNAL_ADD)), db: Session = Depends(get_db)
) -> dict:
    signal = db.get(Signal, signal_id)
    if not signal:
        raise HTTPException(404, "not_found")
    signal.status, signal.error = SignalStatus.ANALYZING.value, None
    db.commit()
    analyze_signal.delay(signal.id)
    db.refresh(signal)
    return serialize_signal(signal)
