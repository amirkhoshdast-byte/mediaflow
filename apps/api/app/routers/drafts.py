import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.ai import SensitiveRoutingError, get_gateway
from app.ai.gateway import extract_json
from app.analysis import check_parts, clean_variants
from app.catalog import LANGUAGES, PERSONAS, PILLARS
from app.db import get_db
from app.deps import current_user, require
from app.enums import RISK_ORDER, Decision, DraftFormat, RiskLevel, Stage
from app.models import Approval, Draft, DraftVersion, Signal, User
from app.permissions import Perm, can_approve, has_perm

router = APIRouter(tags=["drafts"])


def serialize_draft(d: Draft) -> dict:
    return {
        "id": d.id,
        "signal_id": d.signal_id,
        "topic": d.topic,
        "format": d.format,
        "language": d.language,
        "persona": d.persona,
        "pillar": d.pillar,
        "angle": d.angle,
        "generation_group": d.generation_group,
        "parts": d.parts,
        "stage": d.stage,
        "risk": d.risk,
        "checks": check_parts(d.parts),
        "created_at": d.created_at.isoformat(),
        "updated_at": d.updated_at.isoformat(),
        "published_at": d.published_at.isoformat() if d.published_at else None,
    }


# ---------- Studio: generation ----------


class GenerateIn(BaseModel):
    signal_id: str | None = None
    topic: str | None = Field(default=None, max_length=4000)
    format: DraftFormat = DraftFormat.TWEET
    language: str = "fa"
    persona: str = PERSONAS[0]
    pillar: str = PILLARS[0]
    instructions: str = Field(default="", max_length=1000)


@router.post("/studio/generate", status_code=201)
def generate(
    body: GenerateIn, user: User = Depends(require(Perm.DRAFT_EDIT)), db: Session = Depends(get_db)
) -> list[dict]:
    if bool(body.signal_id) == bool(body.topic and body.topic.strip()):
        raise HTTPException(422, "provide_exactly_one_of_signal_or_topic")
    if body.language not in LANGUAGES or body.persona not in PERSONAS or body.pillar not in PILLARS:
        raise HTTPException(422, "invalid_option")

    risk = RiskLevel.MEDIUM.value
    if body.signal_id:
        signal = db.get(Signal, body.signal_id)
        if not signal:
            raise HTTPException(404, "signal_not_found")
        source = f"{signal.title}\n{signal.summary}\n\n{signal.raw_item.text[:4000]}"
        risk = signal.risk or risk
    else:
        source = body.topic.strip()

    try:
        result = get_gateway().run(
            db,
            "content_generation",
            {
                "format": body.format.value,
                "language": body.language,
                "persona": body.persona,
                "pillar": body.pillar,
                "instructions": body.instructions or "none",
                "source": source,
            },
            max_tokens=2500,
        )
        variants = clean_variants(extract_json(result.text), body.format.value)
    except SensitiveRoutingError as e:
        raise HTTPException(500, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"generation_failed: {e.__class__.__name__}") from e

    group = uuid.uuid4().hex
    drafts = []
    for v in variants:
        d = Draft(
            signal_id=body.signal_id,
            topic=None if body.signal_id else source,
            format=body.format.value,
            language=body.language,
            persona=body.persona,
            pillar=body.pillar,
            angle=v["angle"],
            generation_group=group,
            parts=v["parts"],
            stage=Stage.DRAFT.value,
            risk=risk,
            created_by=user.id,
        )
        db.add(d)
        db.flush()
        db.add(DraftVersion(draft_id=d.id, parts=d.parts, author_type="ai", author_id=None))
        drafts.append(d)
    audit.log(db, user.id, "draft.generated", "draft", group, {"count": len(drafts)})
    db.commit()
    return [serialize_draft(d) for d in drafts]


# ---------- Pipeline ----------


@router.get("/drafts")
def list_drafts(_: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    active = db.scalars(
        select(Draft).where(Draft.stage != Stage.PUBLISHED.value).order_by(Draft.updated_at.desc())
    )
    published = db.scalars(
        select(Draft)
        .where(Draft.stage == Stage.PUBLISHED.value)
        .order_by(Draft.published_at.desc())
        .limit(30)
    )
    return [serialize_draft(d) for d in [*active, *published]]


def _get(db: Session, draft_id: str) -> Draft:
    d = db.get(Draft, draft_id)
    if not d:
        raise HTTPException(404, "not_found")
    return d


class DraftPatch(BaseModel):
    parts: list[str] | None = Field(default=None, min_length=1, max_length=10)
    risk: RiskLevel | None = None


@router.patch("/drafts/{draft_id}")
def patch_draft(
    draft_id: str,
    body: DraftPatch,
    user: User = Depends(require(Perm.DRAFT_EDIT)),
    db: Session = Depends(get_db),
) -> dict:
    d = _get(db, draft_id)
    if d.stage == Stage.PUBLISHED.value:
        raise HTTPException(409, "published_is_immutable")
    if body.risk and body.risk.value != d.risk:
        lowering = RISK_ORDER[body.risk] < RISK_ORDER[RiskLevel(d.risk)]
        if lowering and not has_perm(user.role, Perm.DRAFT_LOWER_RISK):
            raise HTTPException(403, "only_reviewers_may_lower_risk")
        audit.log(
            db,
            user.id,
            "draft.risk_changed",
            "draft",
            d.id,
            {"from": d.risk, "to": body.risk.value},
        )
        d.risk = body.risk.value
        d.stage = Stage.DRAFT.value if d.stage == Stage.APPROVED.value else d.stage
    if body.parts is not None:
        parts = [p.strip() for p in body.parts if p.strip()]
        if not parts:
            raise HTTPException(422, "empty_draft")
        if parts != d.parts:
            d.parts = parts
            db.add(DraftVersion(draft_id=d.id, parts=parts, author_type="human", author_id=user.id))
            # Any edit voids earlier review/approval: the text that was approved no longer exists.
            if d.stage in (Stage.TONE_REVIEW.value, Stage.APPROVED.value):
                d.stage = Stage.DRAFT.value
            audit.log(db, user.id, "draft.edited", "draft", d.id)
    db.commit()
    return serialize_draft(d)


class TransitionIn(BaseModel):
    to: Stage
    note: str | None = Field(default=None, max_length=1000)


@router.post("/drafts/{draft_id}/transition")
def transition(
    draft_id: str,
    body: TransitionIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    d = _get(db, draft_id)
    src, dst = Stage(d.stage), body.to

    if (src, dst) == (Stage.DRAFT, Stage.TONE_REVIEW):
        if not has_perm(user.role, Perm.DRAFT_SUBMIT):
            raise HTTPException(403, "forbidden")
        audit.log(db, user.id, "draft.submitted", "draft", d.id)

    elif (src, dst) in ((Stage.TONE_REVIEW, Stage.APPROVED), (Stage.TONE_REVIEW, Stage.DRAFT)):
        # Approving or sending back is a review decision, recorded and gated by risk level.
        if not can_approve(user.role, d.risk):
            raise HTTPException(403, "approval_level_insufficient")
        approved = dst == Stage.APPROVED
        db.add(
            Approval(
                draft_id=d.id,
                approver_id=user.id,
                decision=(Decision.APPROVED if approved else Decision.REJECTED).value,
                note=body.note,
                risk_at_decision=d.risk,
            )
        )
        audit.log(
            db, user.id, "draft.approved" if approved else "draft.rejected", "draft", d.id,
            {"risk": d.risk},
        )  # fmt: skip

    elif (src, dst) == (Stage.APPROVED, Stage.PUBLISHED):
        if not has_perm(user.role, Perm.DRAFT_PUBLISH):
            raise HTTPException(403, "forbidden")
        last = db.scalar(
            select(Approval).where(Approval.draft_id == d.id).order_by(Approval.created_at.desc())
        )
        if (
            not last
            or last.decision != Decision.APPROVED.value
            or RISK_ORDER[RiskLevel(last.risk_at_decision)] < RISK_ORDER[RiskLevel(d.risk)]
        ):
            raise HTTPException(409, "no_valid_approval")
        d.published_at = datetime.now(UTC)
        audit.log(db, user.id, "draft.published", "draft", d.id)

    else:
        raise HTTPException(409, f"transition_not_allowed:{src.value}->{dst.value}")

    d.stage = dst.value
    db.commit()
    return serialize_draft(d)


@router.get("/drafts/{draft_id}/history")
def history(draft_id: str, _: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    _get(db, draft_id)
    versions = db.scalars(
        select(DraftVersion)
        .where(DraftVersion.draft_id == draft_id)
        .order_by(DraftVersion.created_at)
    )
    approvals = db.scalars(
        select(Approval).where(Approval.draft_id == draft_id).order_by(Approval.created_at)
    )
    return {
        "versions": [
            {"parts": v.parts, "author_type": v.author_type, "created_at": v.created_at.isoformat()}
            for v in versions
        ],
        "approvals": [
            {
                "approver_id": a.approver_id,
                "decision": a.decision,
                "note": a.note,
                "risk": a.risk_at_decision,
                "created_at": a.created_at.isoformat(),
            }
            for a in approvals
        ],
    }
