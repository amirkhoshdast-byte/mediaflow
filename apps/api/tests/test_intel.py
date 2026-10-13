from datetime import UTC, datetime, timedelta

from app.db import SessionLocal
from app.enums import Role
from app.models import RawItem, Signal, Source


def _signal(
    db, n, *, relevance, zone="green", risk="low", category="politics", status="ready", age_h=1
):
    item = RawItem(text=f"خبر {n}", content_hash=f"h{n}")
    db.add(item)
    db.flush()
    db.add(
        Signal(
            raw_item_id=item.id, status=status, title=f"عنوان {n}", relevance=relevance, zone=zone,
            risk=risk, category=category, created_at=datetime.now(UTC) - timedelta(hours=age_h),
        )
    )  # fmt: skip


def test_overview_ranks_by_relevance_and_hides_noise(login):
    with SessionLocal() as db:
        _signal(db, 1, relevance=40)
        _signal(db, 2, relevance=90, zone="rebuttal", risk="high", category="information_war")
        _signal(db, 3, relevance=10)  # noise
        _signal(db, 4, relevance=70, zone="red", risk="high", category="security")
        _signal(db, 5, relevance=95, age_h=30)  # older than 24h
        _signal(db, 6, relevance=None, status="analyzing")
        db.commit()
    o = login(Role.ASSISTANT).get("/intel/overview").json()
    assert [s["title"] for s in o["top"]] == ["عنوان 2", "عنوان 4", "عنوان 1"]
    assert o["hidden_low_relevance"] == 1 and o["analyzing"] == 1 and o["total"] == 5
    assert o["by_zone"] == {"rebuttal": 1, "red": 1, "green": 1}
    assert [s["title"] for s in o["rebuttals"]] == ["عنوان 2"]
    assert {s["title"] for s in o["high_risk"]} == {"عنوان 2", "عنوان 4"}


def test_risk_breaks_ties_between_equally_relevant_signals(login):
    with SessionLocal() as db:
        _signal(db, 1, relevance=60, risk="low")
        _signal(db, 2, relevance=60, risk="critical")
        db.commit()
    assert login(Role.ASSISTANT).get("/intel/overview").json()["top"][0]["title"] == "عنوان 2"


def test_overview_reports_intake_health(login):
    with SessionLocal() as db:
        db.query(Source).delete()
        db.add_all(
            [
                Source(
                    type="rss",
                    name="ok",
                    url="https://a.example",
                    last_fetched_at=datetime.now(UTC),
                ),
                Source(type="rss", name="bad", url="https://b.example", last_error="boom"),
                Source(
                    type="rss", name="off", url="https://c.example", active=False, last_error="x"
                ),
            ]
        )
        db.commit()
    s = login(Role.ASSISTANT).get("/intel/overview").json()["sources"]
    assert s["active"] == 2 and s["failing"] == 1 and s["last_fetch"]


def test_overview_requires_login(client):
    assert client.get("/intel/overview").status_code == 401
