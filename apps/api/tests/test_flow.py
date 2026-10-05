from app.enums import Role

LONG = (
    "The foreign ministry announced a new cultural cooperation programme with several partners. "
    * 2
)


def _signal(c):
    r = c.post("/signals", json={"text": LONG})
    assert r.status_code == 201, r.text
    return r.json()


def test_signal_is_analyzed_with_risk_and_approach(login):
    c = login(Role.TREND_ANALYST)
    sig = _signal(c)
    got = [s for s in c.get("/signals").json() if s["id"] == sig["id"]][0]
    assert got["status"] == "ready"
    assert got["risk"] == "low" and got["approach"] == "original_post"
    assert got["title"]


def test_duplicate_item_is_rejected(login):
    c = login(Role.TREND_ANALYST)
    first = _signal(c)
    r = c.post("/signals", json={"text": "  " + LONG.upper()})
    assert r.status_code == 409 and r.json()["detail"]["signal_id"] == first["id"]


def test_failed_analysis_is_visible(login, fake_ai):
    for provider in fake_ai.values():
        provider.analysis = None  # makes json.dumps -> "null" -> no JSON object
    c = login(Role.TREND_ANALYST)
    sig = _signal(c)
    got = [s for s in c.get("/signals").json() if s["id"] == sig["id"]][0]
    assert got["status"] == "failed" and got["error"]


def test_viewer_roles_cannot_add_signal(login):
    assert login(Role.AI_OPERATOR).post("/signals", json={"text": LONG}).status_code == 403


def test_studio_makes_three_distinct_variants(login):
    c = login(Role.CONTENT_LEAD)
    sig = _signal(c)
    r = c.post(
        "/studio/generate", json={"signal_id": sig["id"], "format": "tweet", "language": "fa"}
    )
    assert r.status_code == 201
    drafts = r.json()
    assert len(drafts) == 3 and len({d["angle"] for d in drafts}) == 3
    assert all(d["stage"] == "draft" and d["risk"] == "low" for d in drafts)


def test_studio_requires_exactly_one_source(login):
    c = login(Role.CONTENT_LEAD)
    assert c.post("/studio/generate", json={"format": "tweet"}).status_code == 422
    assert c.post("/studio/generate", json={"topic": "x", "signal_id": "y"}).status_code == 422


def test_studio_flags_overlong_tweet(login, monkeypatch):
    c = login(Role.CONTENT_LEAD)
    d = c.post("/studio/generate", json={"topic": "موضوع"}).json()[0]
    r = c.patch(f"/drafts/{d['id']}", json={"parts": ["x" * 281]})
    assert r.json()["checks"]["too_long"] is True


def _draft(c, risk=None):
    """Draft generated from a (low-risk) analysed signal; risk may only be raised by the lead."""
    sig = _signal(c)
    d = c.post("/studio/generate", json={"signal_id": sig["id"]}).json()[0]
    if risk and risk != "low":
        d = c.patch(f"/drafts/{d['id']}", json={"risk": risk}).json()
    return d


def _as(client, login, role, name):
    login(role, name)
    return client


def test_low_risk_full_chain(client, login):
    lead = login(Role.CONTENT_LEAD)
    d = _draft(lead, "low")
    assert lead.post(f"/drafts/{d['id']}/transition", json={"to": "tone_review"}).status_code == 200
    # Content lead cannot approve her own draft
    assert lead.post(f"/drafts/{d['id']}/transition", json={"to": "approved"}).status_code == 403
    login(Role.DIPLOMATIC_EDITOR)
    ok = client.post(f"/drafts/{d['id']}/transition", json={"to": "approved", "note": "خوب"})
    assert ok.status_code == 200 and ok.json()["stage"] == "approved"
    login(Role.CONTENT_LEAD)
    pub = client.post(f"/drafts/{d['id']}/transition", json={"to": "published"})
    assert pub.json()["stage"] == "published" and pub.json()["published_at"]
    h = client.get(f"/drafts/{d['id']}/history").json()
    assert h["approvals"][0]["decision"] == "approved" and len(h["versions"]) == 1


def test_high_risk_needs_president_office(client, login):
    lead = login(Role.CONTENT_LEAD)
    d = _draft(lead, "high")
    lead.post(f"/drafts/{d['id']}/transition", json={"to": "tone_review"})
    login(Role.DIPLOMATIC_EDITOR)
    assert client.post(f"/drafts/{d['id']}/transition", json={"to": "approved"}).status_code == 403
    login(Role.PRESIDENT_OFFICE)
    assert client.post(f"/drafts/{d['id']}/transition", json={"to": "approved"}).status_code == 200


def test_cannot_skip_to_published(login):
    lead = login(Role.CONTENT_LEAD)
    d = _draft(lead, "low")
    assert lead.post(f"/drafts/{d['id']}/transition", json={"to": "published"}).status_code == 409
    lead.post(f"/drafts/{d['id']}/transition", json={"to": "tone_review"})
    assert lead.post(f"/drafts/{d['id']}/transition", json={"to": "published"}).status_code == 409


def test_edit_after_approval_voids_it(client, login):
    lead = login(Role.CONTENT_LEAD)
    d = _draft(lead, "low")
    lead.post(f"/drafts/{d['id']}/transition", json={"to": "tone_review"})
    login(Role.DIPLOMATIC_EDITOR)
    client.post(f"/drafts/{d['id']}/transition", json={"to": "approved"})
    login(Role.CONTENT_LEAD)
    r = client.patch(f"/drafts/{d['id']}", json={"parts": ["متن تغییریافته"]})
    assert r.json()["stage"] == "draft"
    assert client.post(f"/drafts/{d['id']}/transition", json={"to": "published"}).status_code == 409


def test_risk_can_be_raised_but_only_reviewers_lower_it(client, login):
    lead = login(Role.CONTENT_LEAD)
    d = _draft(lead, "medium")
    assert lead.patch(f"/drafts/{d['id']}", json={"risk": "critical"}).status_code == 200
    assert lead.patch(f"/drafts/{d['id']}", json={"risk": "low"}).status_code == 403
    login(Role.DIPLOMATIC_EDITOR)
    assert client.patch(f"/drafts/{d['id']}", json={"risk": "low"}).status_code == 200


def test_rejection_returns_to_draft_and_is_recorded(client, login):
    lead = login(Role.CONTENT_LEAD)
    d = _draft(lead, "low")
    lead.post(f"/drafts/{d['id']}/transition", json={"to": "tone_review"})
    login(Role.DIPLOMATIC_EDITOR)
    r = client.post(f"/drafts/{d['id']}/transition", json={"to": "draft", "note": "لحن تند"})
    assert r.json()["stage"] == "draft"
    assert client.get(f"/drafts/{d['id']}/history").json()["approvals"][0]["decision"] == "rejected"


def test_stats_count_published_today(client, login):
    lead = login(Role.CONTENT_LEAD)
    d = _draft(lead, "low")
    lead.post(f"/drafts/{d['id']}/transition", json={"to": "tone_review"})
    login(Role.DIPLOMATIC_EDITOR)
    client.post(f"/drafts/{d['id']}/transition", json={"to": "approved"})
    login(Role.CONTENT_LEAD)
    client.post(f"/drafts/{d['id']}/transition", json={"to": "published"})
    s = client.get("/stats/today").json()
    assert s["posts"]["done"] == 1 and s["replies"]["done"] == 0
    assert s["stages"]["published"] == 1
