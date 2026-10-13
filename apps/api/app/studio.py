"""Draft generation and review shared by the Studio endpoint and the automatic drafting task."""

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import audit
from app.ai import get_gateway
from app.ai.gateway import extract_json
from app.analysis import clean_variants
from app.catalog import PERSONAS, PILLAR_FOR_CATEGORY, PILLARS
from app.config import Settings
from app.enums import DraftFormat, RiskLevel, Stage
from app.models import Draft, DraftVersion, RedLine, Signal, ToneReview
from app.tasks import review_draft
from app.tone import escalate_for_issues, parts_hash, rule_issues


class GenerationFailed(Exception):
    pass


def source_text(signal: Signal) -> str:
    return f"{signal.title}\n{signal.summary}\n\n{signal.raw_item.text[:4000]}"


def generate_drafts(
    db: Session,
    *,
    signal: Signal | None,
    topic: str | None,
    fmt: str,
    language: str,
    persona: str,
    pillar: str,
    instructions: str,
    user_id: str | None,
) -> list[Draft]:
    """Three variants from a signal or a topic. `user_id` is None for automatic drafting."""
    risk = (signal.risk if signal else None) or RiskLevel.MEDIUM.value
    source = source_text(signal) if signal else (topic or "").strip()
    try:
        result = get_gateway().run(
            db,
            "content_generation",
            {
                "format": fmt,
                "language": language,
                "persona": persona,
                "pillar": pillar,
                "instructions": instructions or "none",
                "source": source,
            },
            max_tokens=2500,
        )
        variants = clean_variants(extract_json(result.text), fmt)
    except Exception as e:  # noqa: BLE001 - the caller decides how to report it
        raise GenerationFailed(e.__class__.__name__) from e

    group = uuid.uuid4().hex
    drafts = []
    for v in variants:
        d = Draft(
            signal_id=signal.id if signal else None,
            topic=None if signal else source,
            format=fmt,
            language=language,
            persona=persona,
            pillar=pillar,
            angle=v["angle"],
            generation_group=group,
            parts=v["parts"],
            stage=Stage.DRAFT.value,
            risk=risk,
            created_by=user_id,
        )
        db.add(d)
        db.flush()
        db.add(DraftVersion(draft_id=d.id, parts=d.parts, author_type="ai", author_id=None))
        drafts.append(d)
    audit.log(
        db, user_id, "draft.generated", "draft", group,
        {"count": len(drafts), "auto": user_id is None},
    )  # fmt: skip
    db.commit()
    for d in drafts:
        start_review(db, d)
    return drafts


def start_review(db: Session, d: Draft) -> ToneReview:
    """Rule findings are stored (and can raise the risk) at once; the model's judgement follows
    from a worker task."""
    red_lines = list(db.scalars(select(RedLine).where(RedLine.active.is_(True))))
    review = ToneReview(
        draft_id=d.id,
        parts_hash=parts_hash(d.parts),
        parts_snapshot=list(d.parts),
        issues=rule_issues(d.parts, d.language, red_lines),
    )
    db.add(review)
    escalate_for_issues(db, d, review.issues)
    db.commit()
    review_draft.delay(review.id)
    db.refresh(review)
    return review


def auto_draft_signal(db: Session, signal: Signal, settings: Settings) -> list[Draft]:
    """First drafts for a signal worth the owner's attention; [] when it does not qualify.

    Runs for every zone: red-zone topics get drafts too, and they arrive marked high risk."""
    if (
        not settings.auto_draft_enabled
        or (signal.relevance or 0) < settings.auto_draft_min_relevance
    ):
        return []
    if db.scalar(select(Draft.id).where(Draft.signal_id == signal.id)):
        return []  # already drafted (retry, duplicate task)
    day_start = datetime.now(ZoneInfo(settings.timezone)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    done_today = db.scalar(
        select(func.count(func.distinct(Draft.generation_group))).where(
            Draft.created_by.is_(None), Draft.created_at >= day_start
        )
    )
    if (done_today or 0) >= settings.auto_draft_max_per_day:
        return []
    return generate_drafts(
        db,
        signal=signal,
        topic=None,
        fmt=DraftFormat.TWEET.value,
        language=settings.auto_draft_language,
        persona=PERSONAS[0],
        pillar=PILLAR_FOR_CATEGORY.get(signal.category or "", PILLARS[-1]),
        instructions="",
        user_id=None,
    )
