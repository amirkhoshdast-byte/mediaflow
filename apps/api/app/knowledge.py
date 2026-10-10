"""Knowledge base: text extraction, chunking and semantic search (SPEC section 5, phase 1)."""

import io
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway
from app.enums import DocStatus, Sensitivity
from app.models import KnowledgeChunk, KnowledgeDoc

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
CHUNK_CHARS = 900
CHUNK_OVERLAP = 150
_SENTENCE_END = re.compile(r"(?<=[.!?؟؛۔])\s+")


class UnsupportedFile(ValueError):
    pass


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith((".txt", ".md")):
        return data.decode("utf-8", errors="replace")
    if name.endswith(".pdf"):
        from pypdf import PdfReader

        return "\n\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
    if name.endswith(".docx"):
        from docx import Document

        return "\n\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    raise UnsupportedFile(filename)


def _pieces(paragraph: str, size: int) -> list[str]:
    """Split one over-long paragraph on sentence ends, then hard-split what is still too long."""
    out: list[str] = []
    cur = ""
    for sentence in _SENTENCE_END.split(paragraph):
        while len(sentence) > size:
            if cur:
                out.append(cur)
                cur = ""
            out.append(sentence[:size])
            sentence = sentence[size:]
        if cur and len(cur) + len(sentence) + 1 > size:
            out.append(cur)
            cur = ""
        cur = f"{cur} {sentence}".strip()
    if cur:
        out.append(cur)
    return out


def chunk_text(text: str, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    cur = ""
    for paragraph in paragraphs:
        for piece in [paragraph] if len(paragraph) <= size else _pieces(paragraph, size):
            if cur and len(cur) + len(piece) + 2 > size:
                chunks.append(cur)
                tail = cur[-overlap:]
                cur = tail[tail.find(" ") + 1 :] if " " in tail else tail  # start on a word
            cur = f"{cur}\n\n{piece}".strip()
    if cur:
        chunks.append(cur)
    return chunks


def search(
    db: Session, gateway: AIGateway, query: str, limit: int, *, include_sensitive: bool
) -> list[dict]:
    """Nearest chunks across ready documents.

    Vectors are only comparable within one embedding provider, so the query is embedded once per
    provider that actually holds documents (sensitive documents are always local, so the query
    never reaches a cloud provider on their account) and the per-provider hits are merged.
    """
    doc_filter = [KnowledgeDoc.status == DocStatus.READY.value]
    if not include_sensitive:
        doc_filter.append(KnowledgeDoc.sensitivity != Sensitivity.SENSITIVE.value)
    providers = db.scalars(select(KnowledgeDoc.embed_provider).where(*doc_filter).distinct())
    hits: list[dict] = []
    for name in [p for p in providers if p]:
        vector = gateway.provider_named(name).embed([query])[0]
        distance = KnowledgeChunk.embedding.cosine_distance(vector)
        rows = db.execute(
            select(KnowledgeChunk, KnowledgeDoc, distance.label("distance"))
            .join(KnowledgeDoc, KnowledgeDoc.id == KnowledgeChunk.doc_id)
            .where(*doc_filter, KnowledgeDoc.embed_provider == name)
            .order_by(distance)
            .limit(limit)
        )
        hits += [
            {
                "doc_id": doc.id,
                "title": doc.title,
                "doc_type": doc.doc_type,
                "sensitivity": doc.sensitivity,
                "text": chunk.text,
                "score": round(1 - dist, 4),
            }
            for chunk, doc, dist in rows
        ]
    return sorted(hits, key=lambda h: h["score"], reverse=True)[:limit]
