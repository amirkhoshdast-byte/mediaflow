import socket
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app import ingest
from app.config import Settings
from app.db import SessionLocal
from app.enums import Role
from app.models import AuditLog, RawItem, Signal, Source
from app.sources import STARTER, seed_sources

NOW = datetime.now(UTC)


def _rss(*items: tuple[str, str, datetime]) -> bytes:
    body = "".join(
        f"<item><title>{t}</title><link>{link}</link><description>&lt;p&gt;خلاصه&lt;/p&gt;</description>"
        f"<pubDate>{d.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate></item>"
        for t, link, d in items
    )
    return f"<?xml version='1.0'?><rss version='2.0'><channel><title>x</title>{body}</channel></rss>".encode()


def _settings(**kw) -> Settings:
    return Settings(secret_key="x", **kw)


@pytest.fixture
def feeds(monkeypatch):
    """Serve canned feed bodies by URL instead of touching the network."""
    served: dict[str, bytes | Exception] = {}

    def fake_fetch(url, **_):
        body = served[url]
        if isinstance(body, Exception):
            raise body
        return body

    monkeypatch.setattr(ingest, "fetch_bytes", fake_fetch)
    return served


def _source(db, name="A", url="https://a.example/rss", **kw) -> Source:
    s = Source(type="rss", name=name, url=url, **kw)
    db.add(s)
    db.commit()
    return s


# ---------- parsing ----------


def test_rss_entries_are_parsed_and_cleaned():
    (e,) = ingest.parse_rss(_rss(("عنوان آزمون", "https://a.example/1", NOW)))
    assert e.title == "عنوان آزمون" and e.summary == "خلاصه" and e.link == "https://a.example/1"
    assert e.published and abs(e.published - NOW) < timedelta(seconds=5)


def test_gdelt_articles_are_parsed():
    body = b'{"articles":[{"title":"Iran talks resume","url":"https://r.example/1","domain":"r.example","seendate":"20261013T101500Z"}]}'
    (e,) = ingest.parse_gdelt(body)
    assert e.title == "Iran talks resume" and e.published == datetime(
        2026, 10, 13, 10, 15, tzinfo=UTC
    )


def test_gdelt_rejection_text_is_reported_not_swallowed():
    with pytest.raises(ValueError, match="query too short"):
        ingest.parse_gdelt(b"Your query is too short or too long.\nquery too short")


# ---------- ingestion rules ----------


def test_new_entries_become_signals_awaiting_analysis(feeds):
    feeds["https://a.example/rss"] = _rss(
        ("خبر اول", "https://a.example/1", NOW), ("خبر دوم", "https://a.example/2", NOW)
    )
    with SessionLocal() as db:
        s = _source(db)
        ids = ingest.ingest_source(db, s, _settings(), budget=10)
        assert len(ids) == 2
        sig = db.get(Signal, ids[0])
        assert sig.status == "analyzing" and sig.raw_item.source_id == s.id
        assert s.last_error is None and s.last_fetched_at


def test_same_headline_from_two_outlets_is_one_signal(feeds):
    feeds["https://a.example/rss"] = _rss(("Iran Talks Resume", "https://a.example/1", NOW))
    feeds["https://b.example/rss"] = _rss(("iran  talks resume", "https://b.example/9", NOW))
    with SessionLocal() as db:
        a, b = _source(db, "A"), _source(db, "B", "https://b.example/rss")
        assert len(ingest.ingest_source(db, a, _settings(), 10)) == 1
        assert ingest.ingest_source(db, b, _settings(), 10) == []
        assert db.scalar(select(RawItem).where(RawItem.source_id == b.id)) is None


def test_running_twice_does_not_duplicate(feeds):
    feeds["https://a.example/rss"] = _rss(("خبر", "https://a.example/1", NOW))
    with SessionLocal() as db:
        s = _source(db)
        assert len(ingest.ingest_source(db, s, _settings(), 10)) == 1
        assert ingest.ingest_source(db, s, _settings(), 10) == []


def test_old_entries_are_skipped(feeds):
    feeds["https://a.example/rss"] = _rss(("قدیمی", "https://a.example/1", NOW - timedelta(days=3)))
    with SessionLocal() as db:
        assert ingest.ingest_source(db, _source(db), _settings(), 10) == []


def test_run_budget_caps_new_signals(feeds):
    feeds["https://a.example/rss"] = _rss(
        *[(f"خبر {i}", f"https://a.example/{i}", NOW) for i in range(10)]
    )
    with SessionLocal() as db:
        assert len(ingest.ingest_source(db, _source(db), _settings(), budget=3)) == 3


def test_daily_cap_stops_ingest_all(feeds):
    feeds["https://a.example/rss"] = _rss(
        *[(f"خبر {i}", f"https://a.example/{i}", NOW) for i in range(5)]
    )
    with SessionLocal() as db:
        db.query(Source).delete()
        _source(db)
        cfg = _settings(ingest_max_new_per_day=2, ingest_max_new_per_run=40)
        assert len(ingest.ingest_all(db, cfg)) == 2
        assert ingest.ingest_all(db, cfg) == []  # today's allowance is used up


def test_a_dead_feed_is_recorded_and_does_not_stop_the_others(feeds):
    feeds["https://a.example/rss"] = RuntimeError("boom")
    feeds["https://b.example/rss"] = _rss(("خبر سالم", "https://b.example/1", NOW))
    with SessionLocal() as db:
        db.query(Source).delete()
        a, b = _source(db, "A"), _source(db, "B", "https://b.example/rss")
        assert len(ingest.ingest_all(db, _settings())) == 1
        assert "boom" in db.get(Source, a.id).last_error
        assert db.get(Source, b.id).last_error is None


# ---------- SSRF guard ----------


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.5", "192.168.1.9", "169.254.169.254", "::1"])
def test_private_addresses_are_refused(monkeypatch, ip):
    fam = socket.AF_INET6 if ":" in ip else socket.AF_INET
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(fam, 0, 0, "", (ip, 443))])
    with pytest.raises(ingest.UnsafeUrl):
        ingest.check_public_url("https://feed.example/rss")


def test_other_schemes_and_unresolvable_hosts_are_refused(monkeypatch):
    with pytest.raises(ingest.UnsafeUrl):
        ingest.check_public_url("file:///etc/passwd")

    def nxdomain(*a, **k):
        raise socket.gaierror("nope")

    monkeypatch.setattr(socket, "getaddrinfo", nxdomain)
    with pytest.raises(ingest.UnsafeUrl):
        ingest.check_public_url("http://api:8000/admin")


def test_public_address_is_allowed(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, 0, 0, "", ("93.184.216.34", 443))]
    )
    ingest.check_public_url("https://feed.example/rss")


# ---------- starter list and API ----------


def test_starter_sources_are_seeded_once_and_never_restored(login):
    assert len(login(Role.TREND_ANALYST).get("/sources").json()) == len(STARTER)
    c = login(Role.TREND_ANALYST)
    for s in c.get("/sources").json():
        c.delete(f"/sources/{s['id']}")
    with SessionLocal() as db:
        seed_sources(db)  # what every restart does
        assert db.scalar(select(Source)) is None


def test_only_source_managers_change_sources(login):
    body = {"type": "rss", "name": "Test feed", "url": "https://t.example/rss"}
    assert login(Role.CONTENT_LEAD).post("/sources", json=body).status_code == 403
    assert login(Role.CONTENT_LEAD).get("/sources").status_code == 200
    assert login(Role.TREND_ANALYST).post("/sources", json=body).status_code == 201


def test_source_input_is_validated_and_changes_are_audited(login):
    c = login(Role.TREND_ANALYST)
    assert (
        c.post("/sources", json={"type": "rss", "name": "x1", "url": "ftp://t.example"}).status_code
        == 422
    )
    assert c.post("/sources", json={"type": "gdelt", "name": "g1"}).status_code == 422
    assert c.post("/sources", json={"type": "x", "name": "x account"}).status_code == 422
    sid = c.post("/sources", json={"type": "gdelt", "name": "Iran", "query": "Iran"}).json()["id"]
    c.patch(f"/sources/{sid}", json={"active": False})
    c.delete(f"/sources/{sid}")
    with SessionLocal() as db:
        actions = {a.action for a in db.scalars(select(AuditLog))}
    assert {"source.created", "source.updated", "source.deleted"} <= actions


def test_fetch_now_runs_and_analyses_new_items(login, feeds, fake_ai):
    feeds["https://t.example/rss"] = _rss(("خبر تازه", "https://t.example/1", NOW))
    c = login(Role.TREND_ANALYST)
    sid = c.post(
        "/sources", json={"type": "rss", "name": "Test feed", "url": "https://t.example/rss"}
    ).json()["id"]
    assert c.post(f"/sources/{sid}/fetch").status_code == 202
    (sig,) = [s for s in c.get("/signals").json() if s["text"].startswith("خبر تازه")]
    assert sig["status"] == "ready" and sig["zone"] == "green"


def test_beat_schedules_ingestion():
    from app.celery_app import celery

    assert celery.conf.beat_schedule["ingest-all-sources"]["task"] == "ingest.run_all"


def test_atom_feeds_are_parsed_too():
    atom = (
        b"<?xml version='1.0'?><feed xmlns='http://www.w3.org/2005/Atom'><entry><title>Atom item</title>"
        b"<link href='https://a.example/atom/1'/><summary>sum</summary>"
        b"<updated>2026-10-13T10:15:00Z</updated></entry></feed>"
    )
    (e,) = ingest.parse_rss(atom)
    assert e.title == "Atom item" and e.link == "https://a.example/atom/1"
    assert e.published == datetime(2026, 10, 13, 10, 15, tzinfo=UTC)


def test_feeds_without_dates_cannot_replay_their_archive(feeds):
    body = "".join(f"<item><title>archive {i}</title><link>https://a.example/{i}</link></item>" for i in range(30))
    feeds["https://a.example/rss"] = f"<rss><channel>{body}</channel></rss>".encode()
    with SessionLocal() as db:
        assert len(ingest.ingest_source(db, _source(db), _settings(ingest_undated_per_run=5), 40)) == 5


def test_budget_is_shared_so_late_sources_are_not_starved(feeds):
    for name in ("A", "B", "C", "D"):
        feeds[f"https://{name.lower()}.example/rss"] = _rss(
            *[(f"{name} خبر {i}", f"https://{name.lower()}.example/{i}", NOW) for i in range(10)]
        )
    with SessionLocal() as db:
        db.query(Source).delete()
        for name in ("A", "B", "C", "D"):
            _source(db, name, f"https://{name.lower()}.example/rss")
        ids = ingest.ingest_all(db, _settings(ingest_max_new_per_run=8, gdelt_min_interval_seconds=0))
        by_source = {db.get(Signal, i).raw_item.text[0] for i in ids}
    assert len(ids) == 8 and by_source == {"A", "B", "C", "D"}


def test_gdelt_calls_are_spaced(feeds, monkeypatch):
    sleeps = []
    monkeypatch.setattr(ingest.time, "sleep", lambda s: sleeps.append(s))
    with SessionLocal() as db:
        db.query(Source).delete()
        for i in range(3):
            db.add(Source(type="gdelt", name=f"G{i}", query="Iran"))
        db.commit()
        feeds[ingest.gdelt_url("Iran")] = b'{"articles": []}'
        ingest.ingest_all(db, _settings(gdelt_min_interval_seconds=6))
    assert len(sleeps) == 2 and all(0 < s <= 6 for s in sleeps)
