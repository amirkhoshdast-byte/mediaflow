"""Morning overview: what matters in the last 24 hours, ranked, plus the health of the intake."""

from collections import Counter
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.enums import SignalStatus
from app.models import Signal, Source, User
from app.ranking import MIN_RELEVANCE, priority, relevance_of
from app.routers.signals import serialize_signal

router = APIRouter(prefix="/intel", tags=["intel"])

TOP_N = 8


@router.get("/overview")
def overview(_: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    since = datetime.now(UTC) - timedelta(hours=24)
    recent = list(
        db.scalars(
            select(Signal).where(Signal.created_at >= since).order_by(Signal.created_at.desc())
        ).unique()
    )
    ready = [s for s in recent if s.status == SignalStatus.READY.value]
    relevant = sorted(
        (s for s in ready if relevance_of(s) >= MIN_RELEVANCE),
        key=priority,
        reverse=True,
    )
    sources = list(db.scalars(select(Source)))
    fetched = [s.last_fetched_at for s in sources if s.last_fetched_at]
    return {
        "window_hours": 24,
        "total": len(recent),
        "analyzing": sum(s.status == SignalStatus.ANALYZING.value for s in recent),
        "failed": sum(s.status == SignalStatus.FAILED.value for s in recent),
        "hidden_low_relevance": len(ready) - len(relevant),
        "by_zone": dict(Counter(s.zone or "green" for s in relevant)),
        "by_category": dict(Counter(s.category or "other" for s in relevant).most_common(6)),
        "top": [serialize_signal(s) for s in relevant[:TOP_N]],
        "high_risk": [serialize_signal(s) for s in relevant if s.risk in {"high", "critical"}][:5],
        "rebuttals": [serialize_signal(s) for s in relevant if s.zone == "rebuttal"][:5],
        "sources": {
            "active": sum(s.active for s in sources),
            "failing": sum(1 for s in sources if s.active and s.last_error),
            "last_fetch": max(fetched).isoformat() if fetched else None,
        },
    }
