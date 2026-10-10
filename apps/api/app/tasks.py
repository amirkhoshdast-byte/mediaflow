import logging

from sqlalchemy import select

from app.ai import get_gateway
from app.ai.gateway import extract_json
from app.analysis import normalize_analysis
from app.celery_app import celery
from app.db import SessionLocal
from app.enums import DocStatus, Sensitivity, SignalStatus
from app.models import EMBED_DIM, KnowledgeChunk, KnowledgeDoc, Signal

log = logging.getLogger("ncr.tasks")


@celery.task(name="signals.analyze")
def analyze_signal(signal_id: str) -> None:
    with SessionLocal() as db:
        signal = db.get(Signal, signal_id)
        if not signal:
            return
        try:
            result = get_gateway().run(
                db, "signal_analysis", {"text": signal.raw_item.text[:8000]}, max_tokens=800
            )
            for key, value in normalize_analysis(extract_json(result.text)).items():
                setattr(signal, key, value)
            signal.status, signal.error = SignalStatus.READY.value, None
        except Exception as e:  # noqa: BLE001 - any failure must surface on the signal, not vanish
            log.exception("signal analysis failed")
            signal.status = SignalStatus.FAILED.value
            signal.error = f"{e.__class__.__name__}: {str(e)[:300]}"
        db.commit()


EMBED_BATCH = 16


@celery.task(name="kb.embed_doc")
def embed_document(doc_id: str) -> None:
    """(Re-)embed every chunk of a document; sensitive documents embed on a local provider only."""
    with SessionLocal() as db:
        doc = db.get(KnowledgeDoc, doc_id)
        if not doc:
            return
        try:
            chunks = list(
                db.scalars(
                    select(KnowledgeChunk)
                    .where(KnowledgeChunk.doc_id == doc.id)
                    .order_by(KnowledgeChunk.position)
                )
            )
            for i in range(0, len(chunks), EMBED_BATCH):
                batch = chunks[i : i + EMBED_BATCH]
                vectors, provider = get_gateway().embed(
                    [c.text for c in batch], sensitivity=Sensitivity(doc.sensitivity)
                )
                if len(vectors) != len(batch) or any(len(v) != EMBED_DIM for v in vectors):
                    raise ValueError(f"embeddings must have {EMBED_DIM} dimensions")
                for chunk, vector in zip(batch, vectors, strict=True):
                    chunk.embedding = vector
                doc.embed_provider = provider
            doc.status, doc.error = DocStatus.READY.value, None
        except Exception as e:  # noqa: BLE001 - surface on the document, never vanish
            log.exception("document embedding failed")
            doc.status = DocStatus.FAILED.value
            doc.error = f"{e.__class__.__name__}: {str(e)[:300]}"
        db.commit()
