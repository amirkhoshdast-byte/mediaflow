"""Pure post-processing of model output. Models propose; these rules enforce SPEC section 5."""

from app.catalog import CATEGORIES, SENSITIVE_CATEGORIES, TWEET_HARD_LIMIT, TWEET_SOFT_LIMIT
from app.enums import RISK_ORDER, Approach, RiskLevel

_APPROACHES = {a.value for a in Approach}
_RISKS = {r.value for r in RiskLevel}


def normalize_analysis(data: dict) -> dict:
    category = data.get("category") if data.get("category") in CATEGORIES else "other"
    risk = data.get("risk") if data.get("risk") in _RISKS else "medium"
    approach = data.get("approach") if data.get("approach") in _APPROACHES else "monitor_only"
    if category in SENSITIVE_CATEGORIES:
        # Military / security / judicial: never default to engagement, and never low risk.
        if approach not in {Approach.MONITOR_ONLY, Approach.STRATEGIC_SILENCE}:
            approach = Approach.MONITOR_ONLY.value
        if RISK_ORDER[RiskLevel(risk)] < RISK_ORDER[RiskLevel.HIGH]:
            risk = RiskLevel.HIGH.value
    try:
        sentiment = max(-1.0, min(1.0, float(data.get("sentiment", 0))))
    except (TypeError, ValueError):
        sentiment = 0.0
    return {
        "title": str(data.get("title") or "")[:300] or "بدون عنوان",
        "summary": str(data.get("summary") or ""),
        "category": category,
        "region": str(data.get("region") or "")[:80] or None,
        "risk": risk,
        "approach": approach,
        "opportunity": str(data.get("opportunity") or "") or None,
        "sentiment": sentiment,
    }


def clean_variants(data: dict, fmt: str) -> list[dict]:
    variants = data.get("variants")
    if not isinstance(variants, list) or len(variants) < 1:
        raise ValueError("model returned no variants")
    out = []
    for v in variants[:3]:
        parts = [str(p).strip() for p in v.get("parts", []) if str(p).strip()]
        if not parts:
            continue
        if fmt != "thread":
            parts = parts[:1]
        else:
            parts = parts[:10]
        out.append({"angle": str(v.get("angle") or "")[:200] or None, "parts": parts})
    if not out:
        raise ValueError("model returned empty variants")
    return out


def _has_emoji(text: str) -> bool:
    return any(
        0x1F300 <= ord(c) <= 0x1FAFF or 0x2600 <= ord(c) <= 0x27BF or 0x1F000 <= ord(c) <= 0x1F2FF
        for c in text
    )


def check_parts(parts: list[str]) -> dict:
    """Per-draft checks shown in the studio: character counts and rule violations."""
    lengths = [len(p) for p in parts]
    text = "\n".join(parts)
    return {
        "lengths": lengths,
        "too_long": any(n > TWEET_HARD_LIMIT for n in lengths),
        "near_limit": any(TWEET_SOFT_LIMIT < n <= TWEET_HARD_LIMIT for n in lengths),
        "hashtags": sum(p.count("#") for p in parts),
        "too_many_hashtags": any(p.count("#") > 1 for p in parts),
        "has_emoji": _has_emoji(text),
    }
