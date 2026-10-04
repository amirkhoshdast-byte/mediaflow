from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import catalog
from app.config import get_settings
from app.db import get_db
from app.deps import current_user
from app.enums import DraftFormat, Stage
from app.models import Draft, Signal, User

router = APIRouter(tags=["meta"])


@router.get("/meta")
def meta(_: User = Depends(current_user)) -> dict:
    s = get_settings()
    return {
        "categories": catalog.CATEGORIES,
        "personas": catalog.PERSONAS,
        "pillars": catalog.PILLARS,
        "languages": catalog.LANGUAGES,
        "limits": {"soft": catalog.TWEET_SOFT_LIMIT, "hard": catalog.TWEET_HARD_LIMIT},
        "targets": {"posts": s.target_posts_per_day, "replies": s.target_replies_per_day},
    }


@router.get("/stats/today")
def stats_today(_: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    s = get_settings()
    tz = ZoneInfo(s.timezone)
    start = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    published = db.execute(
        select(Draft.format, func.count())
        .where(Draft.stage == Stage.PUBLISHED.value, Draft.published_at >= start)
        .group_by(Draft.format)
    ).all()
    by_format = dict(published)
    replies = by_format.get(DraftFormat.REPLY.value, 0)
    posts = sum(v for k, v in by_format.items() if k != DraftFormat.REPLY.value)
    stage_counts = dict(db.execute(select(Draft.stage, func.count()).group_by(Draft.stage)).all())
    signals_today = db.scalar(
        select(func.count()).select_from(Signal).where(Signal.created_at >= start)
    )
    return {
        "posts": {"done": posts, "target": s.target_posts_per_day},
        "replies": {"done": replies, "target": s.target_replies_per_day},
        "signals_today": signals_today,
        "stages": {st.value: stage_counts.get(st.value, 0) for st in Stage},
    }
