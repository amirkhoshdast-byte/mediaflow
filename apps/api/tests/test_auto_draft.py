from sqlalchemy import select

from app.db import SessionLocal
from app.enums import Role
from app.models import Draft, Signal

NEWS = (
    "The central bank announced on Monday that it will keep its benchmark interest rate unchanged for a "
    "third consecutive meeting, citing slowing inflation and uncertainty in global energy markets."
)


def _analysis(fake_ai, **kw):
    base = {
        "title": "عنوان",
        "summary": "خلاصه",
        "category": "economy",
        "region": "اروپا",
        "risk": "low",
        "approach": "original_post",
        "opportunity": "فرصت",
        "sentiment": 0.1,
        "relevance": 90,
    }
    for provider in fake_ai.values():
        provider.analysis = {**base, **kw}


def _add(login, text=NEWS):
    c = login(Role.ASSISTANT)
    return c.post("/signals", json={"text": text}).json()["id"]


def _drafts():
    with SessionLocal() as db:
        return list(db.scalars(select(Draft).order_by(Draft.created_at)))


def test_a_relevant_signal_gets_three_automatic_drafts(login, fake_ai):
    _analysis(fake_ai)
    sid = _add(login)
    drafts = _drafts()
    assert len(drafts) == 3 and {d.signal_id for d in drafts} == {sid}
    assert all(d.created_by is None and d.language == "en" and d.stage == "draft" for d in drafts)
    assert {d.pillar for d in drafts} == {"economy_development"}
    assert all(d["auto"] for d in login(Role.ASSISTANT).get("/drafts").json())


def test_below_the_relevance_bar_nothing_is_drafted(login, fake_ai):
    _analysis(fake_ai, relevance=69)
    _add(login)
    assert _drafts() == []


def test_a_signal_is_never_drafted_twice(login, fake_ai):
    from app.config import get_settings
    from app.studio import auto_draft_signal

    _analysis(fake_ai)
    sid = _add(login)
    with SessionLocal() as db:
        assert auto_draft_signal(db, db.get(Signal, sid), get_settings()) == []
    assert len(_drafts()) == 3


def test_the_daily_allowance_is_respected(login, fake_ai, monkeypatch):
    from app.config import Settings

    monkeypatch.setenv("AUTO_DRAFT_MAX_PER_DAY", "1")
    from app import config

    config.get_settings.cache_clear()
    try:
        assert Settings(secret_key="x").auto_draft_max_per_day == 1
        _analysis(fake_ai)
        _add(login, NEWS)
        _add(login, NEWS.replace("Monday", "Tuesday"))
        assert len(_drafts()) == 3  # the second signal got none
    finally:
        config.get_settings.cache_clear()


def test_security_topics_are_drafted_too_and_arrive_as_high_risk(login, fake_ai):
    _analysis(fake_ai, category="security", risk="low", approach="monitor_only")
    _add(login)
    drafts = _drafts()
    assert len(drafts) == 3 and {d.risk for d in drafts} == {"high"}
    lead = login(Role.ASSISTANT)
    assert {d["risk"] for d in lead.get("/drafts").json()} == {"high"}


def test_drafting_trouble_never_fails_the_analysis(login, fake_ai):
    _analysis(fake_ai)
    fake_ai["anthropic"].generation_error = RuntimeError("model down")
    sid = _add(login)
    c = login(Role.ASSISTANT)
    sig = next(s for s in c.get("/signals").json() if s["id"] == sid)
    assert sig["status"] == "ready" and _drafts() == []


def test_switch_off(login, fake_ai, monkeypatch):
    from app import config

    monkeypatch.setenv("AUTO_DRAFT_ENABLED", "false")
    config.get_settings.cache_clear()
    try:
        _analysis(fake_ai)
        _add(login)
        assert _drafts() == []
    finally:
        config.get_settings.cache_clear()
