from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.db import get_db
from app.deps import current_user, require
from app.enums import SourceType
from app.models import Source, User
from app.permissions import Perm
from app.tasks import ingest_one

router = APIRouter(prefix="/sources", tags=["sources"])


def serialize(s: Source) -> dict:
    return {
        "id": s.id,
        "type": s.type,
        "name": s.name,
        "url": s.url,
        "query": s.query,
        "language": s.language,
        "domain": s.domain,
        "active": s.active,
        "last_fetched_at": s.last_fetched_at.isoformat() if s.last_fetched_at else None,
        "last_error": s.last_error,
    }


class SourceIn(BaseModel):
    type: SourceType
    name: str = Field(min_length=2, max_length=160)
    url: str | None = Field(default=None, max_length=1000)
    query: str | None = Field(default=None, max_length=500)
    language: str = Field(default="en", max_length=8)
    domain: str | None = Field(default=None, max_length=80)


class SourcePatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    active: bool | None = None


def _get(db: Session, source_id: str) -> Source:
    s = db.get(Source, source_id)
    if not s:
        raise HTTPException(404, "source_not_found")
    return s


@router.get("")
def list_sources(_: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    return [serialize(s) for s in db.scalars(select(Source).order_by(Source.name))]


@router.post("", status_code=201)
def create_source(
    body: SourceIn,
    user: User = Depends(require(Perm.SOURCES_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    if body.type == SourceType.RSS:
        if not body.url or urlparse(body.url).scheme not in {"http", "https"}:
            raise HTTPException(422, "rss_needs_http_url")
    elif body.type == SourceType.GDELT:
        if not body.query:
            raise HTTPException(422, "gdelt_needs_query")
    else:
        raise HTTPException(422, "source_type_not_supported")
    s = Source(
        type=body.type.value,
        name=body.name.strip(),
        url=body.url if body.type == SourceType.RSS else None,
        query=body.query if body.type == SourceType.GDELT else None,
        language=body.language,
        domain=body.domain,
    )
    db.add(s)
    db.flush()
    audit.log(db, user.id, "source.created", "source", s.id, serialize(s))
    db.commit()
    return serialize(s)


@router.patch("/{source_id}")
def update_source(
    source_id: str,
    body: SourcePatch,
    user: User = Depends(require(Perm.SOURCES_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    s = _get(db, source_id)
    before = serialize(s)
    if body.name and body.name.strip():
        s.name = body.name.strip()
    if body.active is not None:
        s.active = body.active
    audit.log(
        db, user.id, "source.updated", "source", s.id, {"before": before, "after": serialize(s)}
    )
    db.commit()
    return serialize(s)


@router.delete("/{source_id}", status_code=204)
def delete_source(
    source_id: str,
    user: User = Depends(require(Perm.SOURCES_MANAGE)),
    db: Session = Depends(get_db),
) -> None:
    s = _get(db, source_id)
    audit.log(db, user.id, "source.deleted", "source", s.id, serialize(s))
    # Signals already created keep their raw item; only the link to the source goes away.
    for item in s.raw_items:
        item.source_id = None
    db.delete(s)
    db.commit()


@router.post("/{source_id}/fetch", status_code=202)
def fetch_now(
    source_id: str, _: User = Depends(require(Perm.SOURCES_MANAGE)), db: Session = Depends(get_db)
) -> dict:
    _get(db, source_id)
    ingest_one.delay(source_id)
    return {"queued": True}
