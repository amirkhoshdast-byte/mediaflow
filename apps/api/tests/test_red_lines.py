from sqlalchemy import select

from app.db import SessionLocal
from app.enums import Role
from app.models import AuditLog, RedLine
from app.red_lines import STARTER, seed_red_lines

NEW = {"kind": "topic", "pattern": "تحریم‌های بانکی", "severity": "high"}


def _audit(action):
    with SessionLocal() as db:
        return list(db.scalars(select(AuditLog).where(AuditLog.action == action)))


def test_starter_list_is_seeded_from_the_voice_guide(login):
    rows = login(Role.CONTENT_LEAD).get("/redlines").json()
    assert len(rows) == len(STARTER)
    assert {"عملیات نظامی", "انتخابات"} <= {r["pattern"] for r in rows}
    assert all(r["active"] for r in rows)


def test_everyone_may_read_but_only_reviewers_may_change(login):
    for role in (Role.CONTENT_LEAD, Role.AI_OPERATOR, Role.SYSADMIN, Role.NARRATIVE_STRATEGIST):
        assert login(role).post("/redlines", json=NEW).status_code == 403
    for role in (Role.DIPLOMATIC_EDITOR, Role.PRESIDENT_OFFICE):
        c = login(role)
        assert c.post("/redlines", json={**NEW, "pattern": f"x-{role.value}"}).status_code == 201


def test_every_change_is_audited_with_before_and_after(login):
    c = login(Role.DIPLOMATIC_EDITOR)
    rid = c.post("/redlines", json=NEW).json()["id"]
    c.patch(f"/redlines/{rid}", json={"severity": "critical", "active": False})
    c.delete(f"/redlines/{rid}")
    assert _audit("redline.created")[0].detail["pattern"] == NEW["pattern"]
    updated = _audit("redline.updated")[0].detail
    assert updated["before"]["severity"] == "high" and updated["after"]["severity"] == "critical"
    assert updated["after"]["active"] is False
    assert _audit("redline.deleted")[0].detail["id"] == rid


def test_duplicates_and_bad_input_are_rejected(login):
    c = login(Role.PRESIDENT_OFFICE)
    assert c.post("/redlines", json=NEW).status_code == 201
    assert c.post("/redlines", json=NEW).status_code == 409
    assert c.post("/redlines", json={**NEW, "severity": "extreme"}).status_code == 422
    assert c.post("/redlines", json={**NEW, "pattern": "x"}).status_code == 422
    assert c.patch("/redlines/missing", json={"active": False}).status_code == 404


def test_seeding_never_restores_what_reviewers_removed(login):
    c = login(Role.DIPLOMATIC_EDITOR)
    for r in c.get("/redlines").json():
        c.delete(f"/redlines/{r['id']}")
    with SessionLocal() as db:
        seed_red_lines(db)  # what every restart does
        assert db.scalar(select(RedLine)) is None
