"""Draft generation and review shared by the Studio endpoint and the automatic drafting task."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.ai import get_gateway
from app.ai.gateway import extract_json
from app.analysis import clean_variants
from app.enums import RiskLevel, Stage
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
