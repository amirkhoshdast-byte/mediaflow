"""Daily intelligence reports at 08:00 and 16:00 Tehran time.

Every section is built from stored data. The model only writes the short opening brief, and a
failure there leaves the report complete without it."""

import json
import logging
from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway
from app.config import Settings
from app.enums import DraftFormat, RiskLevel, Role, SignalStatus, Stage
from app.models import DailyReport, Draft, Notification, Signal, Source, User
from app.ranking import MIN_RELEVANCE, priority, relevance_of

log = logging.getLogger("ncr.reports")

SLOTS = {"morning": time(8, 0), "afternoon": time(16, 0)}
# Roles that read the report; the system administrator never handles content.
RECIPIENT_ROLES = [r.value for r in Role if r != Role.SYSADMIN]
BRIEF_ITEMS = 12


def slot_period(slot: str, day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """The window a scheduled slot covers: 16:00 to 08:00 for the morning, 08:00 to 16:00 after."""
    end_t = SLOTS[slot]
    start_t = SLOTS["afternoon"] if slot == "morning" else SLOTS["morning"]
    end = datetime.combine(day, end_t, tz)
    start = datetime.combine(day - timedelta(days=1) if slot == "morning" else day, start_t, tz)
    return start.astimezone(UTC), end.astimezone(UTC)


def due_slots(now: datetime) -> list[str]:
    """Slots whose time has passed in the last 6 hours (`now` must be timezone-aware, local)."""
    due = []
    for slot, at in SLOTS.items():
        scheduled = datetime.combine(now.date(), at, now.tzinfo)
        if scheduled <= now <= scheduled + timedelta(hours=6):
            due.append(slot)
    return due


def _brief_signal(s: Signal) -> dict:
    return {
        "id": s.id,
        "title": s.title,
        "summary": s.summary,
        "zone": s.zone,
        "risk": s.risk,
        "category": s.category,
        "region": s.region,
        "relevance": relevance_of(s),
        "opportunity": s.opportunity,
    }


def build_content(db: Session, start: datetime, end: datetime, settings: Settings) -> dict:
    ready = [
        s
        for s in db.scalars(
            select(Signal).where(Signal.created_at >= start, Signal.created_at < end)
        ).unique()
        if s.status == SignalStatus.READY.value and relevance_of(s) >= MIN_RELEVANCE
    ]
    ranked = sorted(ready, key=priority, reverse=True)

    tz = ZoneInfo(settings.timezone)
    day_start = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    published = dict(
        db.execute(
            select(Draft.format, func.count())
            .where(Draft.stage == Stage.PUBLISHED.value, Draft.published_at >= day_start)
            .group_by(Draft.format)
        ).all()
    )
    replies = published.get(DraftFormat.REPLY.value, 0)
    in_review = list(db.scalars(select(Draft).where(Draft.stage == Stage.TONE_REVIEW.value)))
    high = {RiskLevel.HIGH.value, RiskLevel.CRITICAL.value}
    sources = list(db.scalars(select(Source).where(Source.active.is_(True))))

    return {
        "counts": {
            "signals": len(ready),
            "by_zone": Counter(s.zone or "green" for s in ready),
            "by_category": dict(Counter(s.category or "other" for s in ready).most_common(6)),
        },
        "top": [_brief_signal(s) for s in ranked[:8]],
        "risks": [_brief_signal(s) for s in ranked if s.risk in high][:6],
        "rebuttals": [_brief_signal(s) for s in ranked if s.zone == "rebuttal"][:5],
        "opportunities": [
            _brief_signal(s)
            for s in ranked
            if s.opportunity and s.zone in {"green", "yellow"} and relevance_of(s) >= 50
        ][:6],
        "pipeline": {
            "stages": dict(
                db.execute(select(Draft.stage, func.count()).group_by(Draft.stage)).all()
            ),
            "waiting_president_office": sum(d.risk in high for d in in_review),
            "waiting_editor": sum(d.risk not in high for d in in_review),
        },
        "targets": {
            "posts": {
                "done": sum(v for k, v in published.items() if k != DraftFormat.REPLY.value),
                "target": settings.target_posts_per_day,
            },
            "replies": {"done": replies, "target": settings.target_replies_per_day},
        },
        "sources": {
            "active": len(sources),
            "failing": sum(1 for s in sources if s.last_error),
        },
    }


def write_brief(db: Session, gateway: AIGateway, content: dict, start: datetime, end: datetime):
    items = [
        {k: s[k] for k in ("title", "zone", "risk", "region")}
        for s in [*content["top"], *content["risks"], *content["rebuttals"]][:BRIEF_ITEMS]
    ]
    result = gateway.run(
        db,
        "daily_brief",
        {
            "period": f"{start.isoformat()} to {end.isoformat()}",
            "pipeline": json.dumps(
                {**content["pipeline"], "targets": content["targets"]}, ensure_ascii=False
            ),
            "items": json.dumps(items, ensure_ascii=False),
        },
        max_tokens=700,
    )
    return result.text.strip()


def notify(db: Session, report: DailyReport) -> int:
    c = report.content
    title = {"morning": "گزارش هوش صبح", "afternoon": "گزارش هوش عصر"}.get(report.slot, "گزارش هوش")
    body = (
        f"{c['counts']['signals']} سیگنال مرتبط، {len(c['risks'])} مورد پرریسک، "
        f"{len(c['rebuttals'])} مورد روایت و پاسخ"
    )
    users = list(
        db.scalars(select(User).where(User.is_active.is_(True), User.role.in_(RECIPIENT_ROLES)))
    )
    for u in users:
        db.add(
            Notification(
                user_id=u.id, kind="report", title=title, body=body, link=f"/reports/{report.id}"
            )
        )
    return len(users)


def generate_report(
    db: Session,
    gateway: AIGateway,
    settings: Settings,
    slot: str,
    *,
    now: datetime | None = None,
) -> DailyReport | None:
    """Build, store and announce one report. A scheduled slot is created once per day."""
    tz = ZoneInfo(settings.timezone)
    now = now or datetime.now(UTC)
    day = now.astimezone(tz).date()
    if slot == "manual":
        start, end = now - timedelta(hours=12), now
    else:
        if db.scalar(
            select(DailyReport.id).where(DailyReport.slot == slot, DailyReport.report_date == day)
        ):
            return None
        start, end = slot_period(slot, day, tz)

    content = build_content(db, start, end, settings)
    report = DailyReport(
        slot=slot, report_date=day, period_start=start, period_end=end, content=content
    )
    try:
        report.brief = write_brief(db, gateway, content, start, end)
    except Exception as e:  # noqa: BLE001 - the data sections are complete without the brief
        log.warning("daily brief failed", exc_info=True)
        report.brief_error = f"{e.__class__.__name__}: {str(e)[:300]}"
    db.add(report)
    db.flush()
    notify(db, report)
    db.commit()
    return report
