from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import audit
from app.ai import get_gateway
from app.config import get_settings
from app.db import get_db
from app.deps import current_user, require
from app.models import DailyReport, Notification, User
from app.permissions import Perm
from app.reports import generate_report

router = APIRouter(tags=["reports"])


def serialize_report(r: DailyReport, *, full: bool = True) -> dict:
    out = {
        "id": r.id,
        "slot": r.slot,
        "report_date": r.report_date.isoformat(),
        "period_start": r.period_start.isoformat(),
        "period_end": r.period_end.isoformat(),
        "created_at": r.created_at.isoformat(),
        "signals": r.content["counts"]["signals"],
    }
    if full:
        out |= {"content": r.content, "brief": r.brief, "brief_error": r.brief_error}
    return out


@router.get("/reports")
def list_reports(_: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(DailyReport).order_by(DailyReport.created_at.desc()).limit(30))
    return [serialize_report(r, full=False) for r in rows]


@router.get("/reports/{report_id}")
def get_report(
    report_id: str, _: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    r = db.get(DailyReport, report_id)
    if not r:
        raise HTTPException(404, "report_not_found")
    return serialize_report(r)


@router.post("/reports/generate", status_code=201)
def generate_now(
    user: User = Depends(require(Perm.REPORT_RUN)), db: Session = Depends(get_db)
) -> dict:
    report = generate_report(db, get_gateway(), get_settings(), "manual", now=datetime.now(UTC))
    audit.log(db, user.id, "report.generated", "daily_report", report.id, {"slot": "manual"})
    db.commit()
    return serialize_report(report)


# ---------- Notifications ----------


def serialize_notification(n: Notification) -> dict:
    return {
        "id": n.id,
        "kind": n.kind,
        "title": n.title,
        "body": n.body,
        "link": n.link,
        "read": n.read_at is not None,
        "created_at": n.created_at.isoformat(),
    }


@router.get("/notifications")
def my_notifications(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    rows = list(
        db.scalars(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(30)
        )
    )
    unread = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
    )
    return {"unread": unread, "items": [serialize_notification(n) for n in rows]}


@router.post("/notifications/read-all")
def read_all(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    for n in db.scalars(
        select(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    ):
        n.read_at = datetime.now(UTC)
    db.commit()
    return {"unread": 0}


@router.post("/notifications/{notification_id}/read")
def read_one(
    notification_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    n = db.get(Notification, notification_id)
    if not n or n.user_id != user.id:  # someone else's notification looks like a missing one
        raise HTTPException(404, "notification_not_found")
    n.read_at = n.read_at or datetime.now(UTC)
    db.commit()
    return serialize_notification(n)
