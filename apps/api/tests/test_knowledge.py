import pytest
from sqlalchemy import select

from app.ai import gateway as gw
from app.config import Settings
from app.db import SessionLocal
from app.enums import Role
from app.knowledge import chunk_text
from app.models import AuditLog

ARCHIVE = "تمدن ایرانی بر گفت‌وگو و حافظه مشترک بنا شده است. حافظ و سعدی صدای این حافظه‌اند."
PROTOCOL = "پروتکل داخلی بحران: تماس با دفتر رئیس پیش از هر موضع رسمی الزامی است."


def _upload(c, text, *, title="سند", sensitivity="normal", filename="a.txt", doc_type="identity"):
    return c.post(
        "/knowledge/docs",
        files={"file": (filename, text.encode(), "text/plain")},
        data={"doc_type": doc_type, "sensitivity": sensitivity, "title": title},
    )


@pytest.fixture
def cloud_embed(fake_ai, monkeypatch):
    """Embedding slot misconfigured to a cloud provider: the worst case for sensitive text."""
    settings = Settings(secret_key="x", ai_provider_embed="anthropic")
    monkeypatch.setattr(gw, "_gateway", gw.AIGateway(settings=settings, providers=fake_ai))
    return fake_ai


# ---------- chunking ----------


def test_chunks_respect_size_and_overlap():
    text = "\n\n".join(f"جمله شماره {i} درباره گفت‌وگوی تمدن‌ها است." * 6 for i in range(12))
    chunks = chunk_text(text, size=300, overlap=60)
    assert len(chunks) > 3 and all(0 < len(c) <= 300 + 60 + 2 for c in chunks)
    assert all(c.strip() for c in chunks)


def test_one_huge_paragraph_is_still_split():
    assert len(chunk_text("کلمه " * 2000, size=500, overlap=50)) > 10


# ---------- upload, status, errors ----------


def test_upload_embeds_and_becomes_ready(login):
    c = login(Role.AI_OPERATOR)
    r = _upload(c, ARCHIVE)
    assert r.status_code == 201
    doc = r.json()
    assert doc["status"] == "ready" and doc["chunks"] >= 1 and doc["error"] is None


def test_only_kb_managers_may_upload_or_delete(login):
    assert _upload(login(Role.CONTENT_LEAD), ARCHIVE).status_code == 403
    doc = _upload(login(Role.AI_OPERATOR), ARCHIVE).json()
    assert login(Role.CONTENT_LEAD).delete(f"/knowledge/docs/{doc['id']}").status_code == 403


def test_rejects_unsupported_and_empty_files(login):
    c = login(Role.AI_OPERATOR)
    assert _upload(c, "x", filename="a.exe").status_code == 415
    assert _upload(c, "   \n\n  ").status_code == 422


def test_embedding_failure_is_visible_and_retryable(login, fake_ai, monkeypatch):
    def boom(texts):
        raise RuntimeError("ollama down")

    c = login(Role.AI_OPERATOR)
    monkeypatch.setattr(fake_ai["ollama"], "embed", boom)
    doc = _upload(c, ARCHIVE).json()
    assert doc["status"] == "failed" and "ollama down" in doc["error"]
    monkeypatch.delattr(fake_ai["ollama"], "embed")  # back to the class implementation
    assert c.post(f"/knowledge/docs/{doc['id']}/retry").json()["status"] == "ready"


def test_delete_removes_document_and_its_search_hits(login):
    c = login(Role.AI_OPERATOR)
    doc = _upload(c, ARCHIVE).json()
    assert c.delete(f"/knowledge/docs/{doc['id']}").status_code == 204
    assert c.post("/knowledge/search", json={"query": "حافظه مشترک"}).json() == []


# ---------- search ----------


def test_search_ranks_the_relevant_document_first(login):
    c = login(Role.AI_OPERATOR)
    _upload(c, ARCHIVE, title="هویت")
    _upload(c, "جدول زمان‌بندی نگهداری ساختمان و تأسیسات سالانه.", title="اداری")
    hits = c.post("/knowledge/search", json={"query": "حافظه مشترک حافظ"}).json()
    assert hits[0]["title"] == "هویت" and hits[0]["score"] > hits[-1]["score"]


# ---------- sensitivity (phase 1 acceptance criterion) ----------


def test_sensitive_document_text_never_reaches_a_cloud_provider(login, cloud_embed):
    c = login(Role.AI_OPERATOR)
    normal = _upload(c, ARCHIVE, title="عمومی").json()
    sensitive = _upload(c, PROTOCOL, title="محرمانه", sensitivity="sensitive").json()
    assert normal["status"] == sensitive["status"] == "ready"
    cloud_seen = [t for batch in cloud_embed["anthropic"].embed_calls for t in batch]
    assert any("حافظ" in t for t in cloud_seen)  # the normal document does use the cloud slot
    assert not any("پروتکل" in t for t in cloud_seen)
    assert any("پروتکل" in t for batch in cloud_embed["ollama"].embed_calls for t in batch)


def test_sensitive_document_fails_closed_when_no_local_provider(login, fake_ai, monkeypatch):
    settings = Settings(secret_key="x", ai_provider_sensitive="anthropic")
    monkeypatch.setattr(gw, "_gateway", gw.AIGateway(settings=settings, providers=fake_ai))
    doc = _upload(login(Role.AI_OPERATOR), PROTOCOL, sensitivity="sensitive").json()
    assert doc["status"] == "failed" and "SensitiveRoutingError" in doc["error"]
    assert fake_ai["anthropic"].embed_calls == []


def test_reclassifying_to_sensitive_re_embeds_locally(login, cloud_embed):
    c = login(Role.AI_OPERATOR)
    doc = _upload(c, PROTOCOL, title="x").json()
    assert cloud_embed["ollama"].embed_calls == []  # started as normal: embedded in the cloud slot
    out = c.patch(f"/knowledge/docs/{doc['id']}", json={"sensitivity": "sensitive"}).json()
    assert out["sensitivity"] == "sensitive" and out["status"] == "ready"
    assert any("پروتکل" in t for batch in cloud_embed["ollama"].embed_calls for t in batch)


def test_search_hides_sensitive_documents_from_other_roles(login):
    ops = login(Role.AI_OPERATOR)
    _upload(ops, PROTOCOL, title="محرمانه", sensitivity="sensitive")
    query = {"query": "پروتکل بحران دفتر رئیس"}
    assert [h["title"] for h in ops.post("/knowledge/search", json=query).json()] == ["محرمانه"]
    assert login(Role.CONTENT_LEAD).post("/knowledge/search", json=query).json() == []
    assert [
        h["title"]
        for h in login(Role.PRESIDENT_OFFICE).post("/knowledge/search", json=query).json()
    ] == ["محرمانه"]


def test_kb_changes_are_audited(login):
    c = login(Role.AI_OPERATOR)
    doc = _upload(c, ARCHIVE).json()
    c.patch(f"/knowledge/docs/{doc['id']}", json={"sensitivity": "sensitive"})
    c.delete(f"/knowledge/docs/{doc['id']}")
    with SessionLocal() as db:
        actions = {a.action for a in db.scalars(select(AuditLog))}
    assert {"kb.uploaded", "kb.reclassified", "kb.deleted"} <= actions
