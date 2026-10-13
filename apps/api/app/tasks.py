import logging

from sqlalchemy import select

from app.ai import get_gateway
from app.ai.gateway import extract_json
from app.analysis import normalize_analysis
from app.celery_app import celery
from app.config import get_settings
from app.db import SessionLocal
from app.enums import SignalStatus
from app.ingest import ingest_all, ingest_source
from app.models import (
    Draft,
    RedLine,
    Signal,
    Source,
    ToneReview,
)
from app.reports import due_slots, generate_report
from app.tone import (
    clean_model_review,
    draft_for_prompt,
    escalate_for_issues,
    parts_hash,
    topics_for_prompt,
)

log = logging.getLogger("ncr.tasks")


@celery.task(name="signals.analyze")
def analyze_signal(signal_id: str) -> None:
    with SessionLocal() as db:
        signal = db.get(Signal, signal_id)
        if not signal:
            return
        try:
            result = get_gateway().run(
                db, "signal_analysis", {"text": signal.raw_item.text[:8000]}, max_tokens=800
            )
            for key, value in normalize_analysis(extract_json(result.text)).items():
                setattr(signal, key, value)
            signal.status, signal.error = SignalStatus.READY.value, None
        except Exception as e:  # noqa: BLE001 - any failure must surface on the signal, not vanish
            log.exception("signal analysis failed")
            signal.status = SignalStatus.FAILED.value
            signal.error = f"{e.__class__.__name__}: {str(e)[:300]}"
        db.commit()


@celery.task(name="ingest.run_all")
def ingest_all_sources() -> int:
    with SessionLocal() as db:
        created = ingest_all(db, get_settings())
    for signal_id in created:
        analyze_signal.delay(signal_id)
    return len(created)


@celery.task(name="ingest.run_source")
def ingest_one(source_id: str) -> int:
    settings = get_settings()
    with SessionLocal() as db:
        source = db.get(Source, source_id)
        if not source:
            return 0
        created = ingest_source(db, source, settings, settings.ingest_max_new_per_run)
    for signal_id in created:
        analyze_signal.delay(signal_id)
    return len(created)


@celery.task(name="tone.review_draft")
def review_draft(review_id: str) -> None:
    """Add the model's judgement to a review that already holds the rule findings."""
    with SessionLocal() as db:
        review = db.get(ToneReview, review_id)
        draft = db.get(Draft, review.draft_id) if review else None
        if not review or not draft:
            return
        try:
            red_lines = list(db.scalars(select(RedLine).where(RedLine.active.is_(True))))
            result = get_gateway().run(
                db,
                "tone_review",
                {
                    "language": draft.language,
                    "topics": topics_for_prompt(red_lines),
                    "draft": draft_for_prompt(review.parts_snapshot),
                },
                max_tokens=1500,
            )
            parsed = clean_model_review(
                extract_json(result.text), red_lines, len(review.parts_snapshot)
            )
            review.issues = [*review.issues, *parsed["issues"]]
            if review.parts_hash == parts_hash(
                draft.parts
            ):  # a stale review must not move the risk
                escalate_for_issues(db, draft, parsed["issues"])
            review.score, review.suggested_parts = parsed["score"], parsed["suggested_parts"]
            review.provider, review.status, review.error = result.provider, "ready", None
        except Exception as e:  # noqa: BLE001 - rule findings stay available even if the model fails
            log.exception("tone review failed")
            review.status = "failed"
            review.error = f"{e.__class__.__name__}: {str(e)[:300]}"
        db.commit()


@celery.task(name="reports.generate")
def generate_scheduled_report(slot: str) -> str | None:
    with SessionLocal() as db:
        report = generate_report(db, get_gateway(), get_settings(), slot)
        return report.id if report else None


@celery.task(name="reports.catch_up")
def catch_up_reports() -> list[str]:
    """Create a slot's report if its time passed (within 6 hours) and it was never made."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo(get_settings().timezone))
    return [slot for slot in due_slots(now) if generate_scheduled_report(slot)]
