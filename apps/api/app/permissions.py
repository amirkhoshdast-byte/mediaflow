"""Role-based access control. Pure functions, no I/O, unit-tested (SPEC section 3)."""

from enum import StrEnum

from app.enums import RISK_ORDER, RiskLevel, Role


class Perm(StrEnum):
    SOURCES_MANAGE = "sources:manage"
    SIGNAL_ADD = "signal:add"
    DRAFT_EDIT = "draft:edit"
    DRAFT_SUBMIT = "draft:submit"
    DRAFT_PUBLISH = "draft:publish"
    DRAFT_LOWER_RISK = "draft:lower_risk"
    APPROVE_LOW_MEDIUM = "approve:low_medium"
    APPROVE_HIGH_CRITICAL = "approve:high_critical"
    PROMPTS_MANAGE = "prompts:manage"
    USERS_MANAGE = "users:manage"
    AUDIT_VIEW = "audit:view"


R = Role
PERMISSIONS: dict[Role, set[Perm]] = {
    R.TREND_ANALYST: {Perm.SOURCES_MANAGE, Perm.SIGNAL_ADD},
    R.MEDIA_MONITOR: {Perm.SIGNAL_ADD},
    R.AI_OPERATOR: {Perm.PROMPTS_MANAGE},
    R.CONTENT_LEAD: {Perm.SIGNAL_ADD, Perm.DRAFT_EDIT, Perm.DRAFT_SUBMIT, Perm.DRAFT_PUBLISH},
    R.NARRATIVE_STRATEGIST: {Perm.SIGNAL_ADD, Perm.DRAFT_EDIT, Perm.DRAFT_PUBLISH},
    R.DIPLOMATIC_EDITOR: {
        Perm.DRAFT_EDIT,
        Perm.DRAFT_LOWER_RISK,
        Perm.APPROVE_LOW_MEDIUM,
    },
    R.PRESIDENT_OFFICE: {
        Perm.DRAFT_LOWER_RISK,
        Perm.APPROVE_LOW_MEDIUM,
        Perm.APPROVE_HIGH_CRITICAL,
        Perm.AUDIT_VIEW,
    },
    # System admin manages users/settings but can never approve content.
    R.SYSADMIN: {Perm.USERS_MANAGE, Perm.AUDIT_VIEW},
}


def has_perm(role: str, perm: Perm) -> bool:
    try:
        return perm in PERMISSIONS[Role(role)]
    except (KeyError, ValueError):
        return False


def can_approve(role: str, risk: str) -> bool:
    """Low/medium: Diplomatic Editor (or President's Office). High/critical: President's Office only."""
    needed = (
        Perm.APPROVE_HIGH_CRITICAL
        if RISK_ORDER[RiskLevel(risk)] >= RISK_ORDER[RiskLevel.HIGH]
        else Perm.APPROVE_LOW_MEDIUM
    )
    return has_perm(role, needed)
