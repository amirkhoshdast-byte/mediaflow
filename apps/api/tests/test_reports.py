from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.ai import gateway as gw
from app.config import Settings
from app.db import SessionLocal
from app.enums import Role
from app.models import DailyReport, Draft, Notification, RawItem, Signal, User
from app.reports import build_content, due_slots, generate_report, slot_period

TZ = ZoneInfo("Asia/Tehran")
CFG = Settings(secret_key="x")
NOW = datetime(2026, 10, 14, 9, 0, tzinfo=TZ).astimezone(UTC)  # 09:00 Tehran


def _signal(db, n, *, at, relevance=70, zone="green", risk="low", category="politics",
            opportunity=None, status="ready"):  # fmt: skip
    item = RawItem(text=f"خبر {n}", content_hash=f"r{n}")
    db.add(item)
    db.flush()
    db.add(
        Signal(raw_item_id=item.id, status=status, title=f"عنوان {n}", summary="خلاصه", relevance=relevance,
               zone=zone, risk=risk, category=category, opportunity=opportunity, created_at=at)
    )  # fmt: skip


def _gateway(fake_ai):
    return gw.AIGateway(settings=CFG, providers=fake_ai)


# ---------- windows ----------


def test_morning_covers_yesterday_afternoon_and_night_afternoon_covers_the_working_day():
    day = datetime(2026, 10, 14).date()
    m_start, m_end = (t.astimezone(TZ) for t in slot_period("morning", day, TZ))
    a_start, a_end = (t.astimezone(TZ) for t in slot_period("afternoon", day, TZ))
    assert (m_start.day, m_start.hour, m_end.day, m_end.hour) == (13, 16, 14, 8)
    assert (a_start.day, a_start.hour, a_end.day, a_end.hour) == (14, 8, 14, 16)
    assert m_end == a_start  # no gap and no overlap between consecutive reports


def test_catch_up_only_covers_slots_that_just_passed():
    at = lambda h, m=0: datetime(2026, 10, 14, h, m, tzinfo=TZ)  # noqa: E731
    assert due_slots(at(7, 59)) == []
    assert due_slots(at(8, 0)) == ["morning"]
    assert due_slots(at(13, 0)) == ["morning"]
    assert due_slots(at(14, 30)) == []  # too late to produce the morning report
    assert due_slots(at(16, 10)) == ["afternoon"]
    assert due_slots(at(23, 0)) == []


# ---------- content ----------


def test_content_is_ranked_windowed_and_split_into_sections(login):
    start, end = slot_period("afternoon", NOW.astimezone(TZ).date(), TZ)
    inside = start + timedelta(hours=2)
    with SessionLocal() as db:
        _signal(db, 1, at=inside, relevance=60, opportunity="فرصت گفت‌وگو")
        _signal(
            db, 2, at=inside, relevance=90, zone="rebuttal", risk="high", category="information_war"
        )
        _signal(db, 3, at=inside, relevance=10)  # noise
        _signal(db, 4, at=start - timedelta(hours=1), relevance=99)  # before the window
        _signal(db, 5, at=inside, relevance=80, zone="red", risk="critical", category="security")
        _signal(db, 6, at=inside, status="analyzing")
        db.commit()
        c = build_content(db, start, end, CFG)
    assert [s["title"] for s in c["top"]] == ["عنوان 2", "عنوان 5", "عنوان 1"]
    assert c["counts"]["signals"] == 3
    assert {s["title"] for s in c["risks"]} == {"عنوان 2", "عنوان 5"}
    assert [s["title"] for s in c["rebuttals"]] == ["عنوان 2"]
    assert [s["title"] for s in c["opportunities"]] == ["عنوان 1"]


def test_opportunities_need_relevance_and_a_calm_zone(login):
    start, end = slot_period("afternoon", NOW.astimezone(TZ).date(), TZ)
    with SessionLocal() as db:
        _signal(db, 1, at=start + timedelta(hours=1), relevance=60, opportunity="فرصت یک")
        _signal(db, 2, at=start + timedelta(hours=1), relevance=40, opportunity="فرصت کم‌ارتباط")
        _signal(
            db, 3, at=start + timedelta(hours=1), relevance=90, zone="red", opportunity="فرصت قرمز"
        )
        db.commit()
        c = build_content(db, start, end, CFG)
    assert [o["opportunity"] for o in c["opportunities"]] == ["فرصت یک"]


def test_pipeline_counts_open_drafts_and_flags_the_high_risk_ones(login):
    with SessionLocal() as db:
        for risk in ("low", "medium", "high", "critical"):
            db.add(
                Draft(
                    format="tweet",
                    language="fa",
                    persona="x",
                    pillar="y",
                    parts=["t"],
                    stage="draft",
                    risk=risk,
                )
            )
        db.commit()
        c = build_content(db, NOW - timedelta(hours=8), NOW, CFG)
    assert c["pipeline"]["awaiting_approval"] == 4 and c["pipeline"]["high_risk_open"] == 2


# ---------- generation ----------


def test_a_scheduled_slot_is_generated_once_per_day(login, fake_ai):
    with SessionLocal() as db:
        first = generate_report(db, _gateway(fake_ai), CFG, "morning", now=NOW)
        again = generate_report(db, _gateway(fake_ai), CFG, "morning", now=NOW)
        other = generate_report(db, _gateway(fake_ai), CFG, "afternoon", now=NOW)
        assert first and again is None and other
        assert db.query(DailyReport).count() == 2
    assert first.brief == "خلاصه آزمون برای این بازه."


def test_report_is_complete_without_the_model_brief(login, fake_ai):
    fake_ai["anthropic"].brief = RuntimeError("model down")
    start, _ = slot_period("afternoon", NOW.astimezone(TZ).date(), TZ)
    with SessionLocal() as db:
        _signal(db, 1, at=start + timedelta(hours=1), relevance=70)
        db.commit()
        r = generate_report(db, _gateway(fake_ai), CFG, "afternoon", now=NOW)
        assert r.brief is None and "model down" in r.brief_error
        assert r.content["counts"]["signals"] == 1


def test_brief_prompt_holds_only_period_items_inside_the_data_block(login, fake_ai):
    start, _ = slot_period("afternoon", NOW.astimezone(TZ).date(), TZ)
    with SessionLocal() as db:
        _signal(db, 1, at=start + timedelta(hours=1))
        _signal(db, 2, at=start - timedelta(hours=3))
        db.commit()
        generate_report(db, _gateway(fake_ai), CFG, "afternoon", now=NOW)
    system, user = next(c for c in fake_ai["anthropic"].calls if "Items from the period" in c[1])
    assert "عنوان 1" in user and "عنوان 2" not in user
    assert "<untrusted_input>" in user and "never add facts" in system


def test_everyone_but_the_sysadmin_and_inactive_users_is_notified(login, fake_ai, make_user):
    make_user("lead", Role.ASSISTANT)
    make_user("boss", Role.OWNER)
    make_user("admin2", Role.SYSADMIN)
    make_user("gone", Role.ASSISTANT)
    with SessionLocal() as db:
        db.execute(select(User))
        for u in db.scalars(select(User).where(User.username == "gone")):
            u.is_active = False
        db.commit()
        r = generate_report(db, _gateway(fake_ai), CFG, "morning", now=NOW)
        names = {db.get(User, n.user_id).username for n in db.scalars(select(Notification))}
        assert {n.link for n in db.scalars(select(Notification))} == {f"/reports/{r.id}"}
    # the bootstrap admin is an owner, so it is a recipient as well
    assert {"lead", "boss"} <= names and not names & {"admin2", "gone"}


# ---------- API ----------


def test_manual_run_needs_the_report_permission(login):
    assert login(Role.ASSISTANT).post("/reports/generate").status_code == 403
    r = login(Role.OWNER).post("/reports/generate")
    assert r.status_code == 201 and r.json()["slot"] == "manual" and r.json()["brief"]


def test_reports_are_readable_by_any_signed_in_user(login, client):
    rid = login(Role.OWNER).post("/reports/generate").json()["id"]
    c = login(Role.ASSISTANT)
    assert [r["id"] for r in c.get("/reports").json()] == [rid]
    assert c.get(f"/reports/{rid}").json()["content"]["counts"]["signals"] == 0
    assert c.get("/reports/missing").status_code == 404
    client.cookies.clear()
    assert client.get("/reports").status_code == 401


def test_notifications_can_be_read_and_belong_to_their_owner(login, make_user):
    make_user("u_assistant", Role.ASSISTANT)  # recipients must exist when the report runs
    make_user("u_owner", Role.OWNER)
    login(Role.OWNER).post("/reports/generate")  # notifies everyone but the sysadmin
    c = login(Role.ASSISTANT)
    box = c.get("/notifications").json()
    assert box["unread"] == 1 and box["items"][0]["link"].startswith("/reports/")
    nid = box["items"][0]["id"]
    assert c.post(f"/notifications/{nid}/read").json()["read"] is True
    assert c.get("/notifications").json()["unread"] == 0
    other = login(Role.OWNER)
    assert other.post(f"/notifications/{nid}/read").status_code == 404  # not theirs
    assert other.post("/notifications/read-all").json() == {"unread": 0}
    assert other.get("/notifications").json()["unread"] == 0


def test_beat_runs_reports_at_8_and_16_tehran_time():
    from app.celery_app import celery

    s = celery.conf.beat_schedule
    assert s["report-morning"]["schedule"].hour == {8} and s["report-afternoon"][
        "schedule"
    ].hour == {16}
    assert s["report-morning"]["args"] == ("morning",) and "report-catch-up" in s
