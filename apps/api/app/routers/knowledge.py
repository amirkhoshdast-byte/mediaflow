from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import audit
from app.ai import get_gateway
from app.db import get_db
from app.deps import current_user, require
from app.enums import DocStatus, DocType, Sensitivity
from app.knowledge import MAX_UPLOAD_BYTES, UnsupportedFile, chunk_text, extract_text, search
from app.models import KnowledgeChunk, KnowledgeDoc, User
from app.permissions import Perm, has_perm
from app.tasks import embed_document

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def serialize_doc(db: Session, d: KnowledgeDoc) -> dict:
    count = db.scalar(select(func.count()).where(KnowledgeChunk.doc_id == d.id))
    return {
        "id": d.id,
        "title": d.title,
        "doc_type": d.doc_type,
        "sensitivity": d.sensitivity,
        "filename": d.filename,
        "status": d.status,
        "error": d.error,
        "chunks": count,
        "created_at": d.created_at.isoformat(),
    }


def _get(db: Session, doc_id: str) -> KnowledgeDoc:
    doc = db.get(KnowledgeDoc, doc_id)
    if not doc:
        raise HTTPException(404, "document_not_found")
    return doc


def _reprocess(db: Session, doc: KnowledgeDoc) -> None:
    """Drop old vectors (they may sit in another provider's space) and embed again."""
    for chunk in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc.id)):
        chunk.embedding = None
    doc.status, doc.error, doc.embed_provider = DocStatus.PROCESSING.value, None, None
    db.commit()
    embed_document.delay(doc.id)
    db.refresh(doc)


@router.get("/docs")
def list_docs(_: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(KnowledgeDoc).order_by(KnowledgeDoc.created_at.desc()))
    return [serialize_doc(db, d) for d in rows]


@router.post("/docs", status_code=201)
async def upload_doc(
    file: UploadFile = File(...),
    doc_type: DocType = Form(...),
    sensitivity: Sensitivity = Form(Sensitivity.NORMAL),
    title: str = Form(default=""),
    user: User = Depends(require(Perm.KB_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "file_too_large")
    filename = file.filename or "document"
    try:
        text = extract_text(filename, data)
    except UnsupportedFile as e:
        raise HTTPException(415, "unsupported_file_type") from e
    except Exception as e:  # noqa: BLE001 - corrupt PDF/DOCX
        raise HTTPException(422, "unreadable_file") from e
    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(422, "empty_document")
    doc = KnowledgeDoc(
        title=title.strip()[:300] or filename,
        doc_type=doc_type.value,
        sensitivity=sensitivity.value,
        filename=filename[:300],
        created_by=user.id,
    )
    db.add(doc)
    db.flush()
    db.add_all(KnowledgeChunk(doc_id=doc.id, position=i, text=t) for i, t in enumerate(chunks))
    audit.log(
        db, user.id, "kb.uploaded", "knowledge_doc", doc.id,
        {"sensitivity": doc.sensitivity, "doc_type": doc.doc_type, "chunks": len(chunks)},
    )  # fmt: skip
    db.commit()
    embed_document.delay(doc.id)
    db.refresh(doc)
    return serialize_doc(db, doc)


class DocPatch(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    doc_type: DocType | None = None
    sensitivity: Sensitivity | None = None


@router.patch("/docs/{doc_id}")
def patch_doc(
    doc_id: str,
    body: DocPatch,
    user: User = Depends(require(Perm.KB_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    doc = _get(db, doc_id)
    if body.title and body.title.strip():
        doc.title = body.title.strip()
    if body.doc_type:
        doc.doc_type = body.doc_type.value
    reclassified = body.sensitivity and body.sensitivity.value != doc.sensitivity
    if reclassified:
        audit.log(
            db, user.id, "kb.reclassified", "knowledge_doc", doc.id,
            {"from": doc.sensitivity, "to": body.sensitivity.value},
        )  # fmt: skip
        doc.sensitivity = body.sensitivity.value
    db.commit()
    if reclassified:
        _reprocess(db, doc)
    return serialize_doc(db, doc)


@router.post("/docs/{doc_id}/retry")
def retry_doc(
    doc_id: str, _: User = Depends(require(Perm.KB_MANAGE)), db: Session = Depends(get_db)
) -> dict:
    doc = _get(db, doc_id)
    _reprocess(db, doc)
    return serialize_doc(db, doc)


@router.delete("/docs/{doc_id}", status_code=204)
def delete_doc(
    doc_id: str, user: User = Depends(require(Perm.KB_MANAGE)), db: Session = Depends(get_db)
) -> None:
    doc = _get(db, doc_id)
    audit.log(db, user.id, "kb.deleted", "knowledge_doc", doc.id, {"title": doc.title})
    db.query(KnowledgeChunk).filter(KnowledgeChunk.doc_id == doc.id).delete()
    db.delete(doc)
    db.commit()


class SearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    limit: int = Field(default=5, ge=1, le=20)


@router.post("/search")
def search_docs(
    body: SearchIn, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[dict]:
    try:
        return search(
            db,
            get_gateway(),
            body.query,
            body.limit,
            include_sensitive=has_perm(user.role, Perm.KB_READ_SENSITIVE),
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"search_failed: {e.__class__.__name__}") from e
