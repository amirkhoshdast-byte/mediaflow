"""Tone review: deterministic checks plus sanitising of the model's opinion.

Rules decide what can be decided exactly (red-line wording, office language, format limits);
the model is asked only for judgement (tone, facts, red-line *topics*). Whatever it returns is
untrusted: a red line it cites must exist in the active list, and severities come from that list,
never from the model."""

import hashlib
import json
import re

from app import audit
from app.analysis import check_parts
from app.enums import RISK_ORDER, RedLineKind, RiskLevel, Stage
from app.models import Draft, RedLine

# Bureaucratic wording the voice guide bans outright (Persian drafts only).
OFFICE_WORDS = [
    "در راستای", "لازم به ذکر است", "می‌نماید", "نمود", "بی‌بدیل", "مذکور", "فلذا", "علی‌ایحال",
    "شایان ذکر است",
]  # fmt: skip

_ARABIC_LETTERS = str.maketrans({"ي": "ی", "ك": "ک", "ۀ": "ه", "ة": "ه", "أ": "ا", "إ": "ا"})
_MARKS = re.compile(r"[‌‍ً-ٰٟ]")  # ZWNJ, ZWJ, Arabic diacritics
MODEL_ISSUE_TYPES = {"tone", "red_line_topic", "fact", "other"}


def normalize(text: str) -> str:
    """Spelling-insensitive form: Arabic/Persian letter variants, ZWNJ and diacritics removed."""
    return re.sub(r"\s+", " ", _MARKS.sub("", text.translate(_ARABIC_LETTERS))).strip().casefold()


def parts_hash(parts: list[str]) -> str:
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()


def _issue(source: str, type_: str, reason: str, **extra) -> dict:
    base = {"source": source, "type": type_, "quote": None, "reason": reason, "severity": None}
    return {**base, "red_line_id": None, "suggestion": None, "part": None, **extra}


def rule_issues(parts: list[str], language: str, red_lines: list[RedLine]) -> list[dict]:
    issues: list[dict] = []
    for i, part in enumerate(parts):
        flat = normalize(part)
        for r in red_lines:
            if r.kind == RedLineKind.PHRASE.value and normalize(r.pattern) in flat:
                issues.append(
                    _issue("rule", "red_line_phrase", r.description or "عبارت ممنوع در فهرست خطوط قرمز",
                           quote=r.pattern, severity=r.severity, red_line_id=r.id, part=i)
                )  # fmt: skip
        if language == "fa":
            for word in OFFICE_WORDS:
                if normalize(word) in flat:
                    issues.append(
                        _issue("rule", "office_language", "واژه اداری؛ راهنمای صدا آن را ممنوع کرده است",
                               quote=word, part=i)
                    )  # fmt: skip
    checks = check_parts(parts)
    if checks["too_long"]:
        issues.append(_issue("rule", "format", "طول توییت بیش از ۲۸۰ نویسه است"))
    if checks["too_many_hashtags"]:
        issues.append(_issue("rule", "format", "بیش از یک هشتگ"))
    if checks["has_emoji"]:
        issues.append(_issue("rule", "format", "ایموجی مجاز نیست"))
    return issues


def topics_for_prompt(red_lines: list[RedLine]) -> str:
    topics = [f"- {r.pattern}" for r in red_lines if r.kind == RedLineKind.TOPIC.value]
    return "\n".join(topics) or "none"


def draft_for_prompt(parts: list[str]) -> str:
    return "\n".join(f"{i + 1}. {p}" for i, p in enumerate(parts))


def clean_model_review(data: dict, red_lines: list[RedLine], n_parts: int) -> dict:
    topics = {normalize(r.pattern): r for r in red_lines if r.kind == RedLineKind.TOPIC.value}
    issues: list[dict] = []
    raw_issues = data.get("issues")
    for item in (raw_issues if isinstance(raw_issues, list) else [])[:12]:
        if not isinstance(item, dict):
            continue
        reason = str(item.get("reason") or "").strip()[:500]
        if not reason:
            continue
        type_ = item.get("type") if item.get("type") in MODEL_ISSUE_TYPES else "other"
        line = None
        if type_ == "red_line_topic":
            line = topics.get(normalize(str(item.get("red_line") or "")))
            if line is None:  # the model may not invent red lines
                type_ = "tone"
        issues.append(
            _issue(
                "model",
                type_,
                reason,
                quote=str(item.get("quote") or "").strip()[:300] or None,
                suggestion=str(item.get("suggestion") or "").strip()[:500] or None,
                severity=line.severity if line else None,
                red_line_id=line.id if line else None,
            )  # fmt: skip
        )
    try:
        score = max(0, min(100, int(data.get("score"))))
    except (TypeError, ValueError):
        score = None
    suggested = data.get("suggested_parts")
    if isinstance(suggested, list):
        suggested = [str(p).strip() for p in suggested]
        if len(suggested) != n_parts or not all(suggested):
            suggested = None  # a rewrite that changes the shape is not a drop-in suggestion
    else:
        suggested = None
    return {"issues": issues, "score": score, "suggested_parts": suggested}


def escalation_floor(issues: list[dict]) -> RiskLevel | None:
    """The highest severity any finding carries; only red-line findings carry one."""
    levels = [RiskLevel(i["severity"]) for i in issues if i.get("severity")]
    return max(levels, key=RISK_ORDER.__getitem__, default=None)


def escalate_for_issues(db, draft: Draft, issues: list[dict]) -> bool:
    """Raise the draft's risk to the strongest finding. Risk never goes down here, and an approval
    given at a lower level is voided (the draft returns to editing) because it no longer matches."""
    floor = escalation_floor(issues)
    if floor is None or RISK_ORDER[floor] <= RISK_ORDER[RiskLevel(draft.risk)]:
        return False
    reasons = [i.get("quote") or i["reason"] for i in issues if i.get("severity") == floor.value]
    audit.log(
        db, None, "draft.risk_escalated", "draft", draft.id,
        {"from": draft.risk, "to": floor.value, "because": reasons[:5]},
    )  # fmt: skip
    draft.risk = floor.value
    if draft.stage == Stage.APPROVED.value:
        draft.stage = Stage.DRAFT.value
        audit.log(
            db, None, "draft.approval_voided", "draft", draft.id, {"reason": "risk_escalated"}
        )
    return True
