"""Role-based access control. Pure functions, no I/O, unit-tested (PRODUCT.md section 3).

Three roles: the account owner does everything, an assistant prepares material but never decides,
and the system administrator manages users but never touches content."""

from enum import StrEnum

from app.enums import Role


class Perm(StrEnum):
    SOURCES_MANAGE = "sources:manage"
    SIGNAL_ADD = "signal:add"
    DRAFT_EDIT = "draft:edit"
    DRAFT_APPROVE = "draft:approve"
    DRAFT_PUBLISH = "draft:publish"
    DRAFT_LOWER_RISK = "draft:lower_risk"
    REDLINE_MANAGE = "redline:manage"
    REPORT_RUN = "report:run"
    USERS_MANAGE = "users:manage"
    AUDIT_VIEW = "audit:view"


R = Role
PERMISSIONS: dict[Role, set[Perm]] = {
    R.OWNER: set(Perm),
    # Prepares: adds news, edits drafts, curates sources. Cannot approve, publish, lower a risk
    # level or change the red lines.
    R.ASSISTANT: {Perm.SIGNAL_ADD, Perm.DRAFT_EDIT, Perm.SOURCES_MANAGE},
    # Manages users/settings but can never approve content.
    R.SYSADMIN: {Perm.USERS_MANAGE, Perm.AUDIT_VIEW},
}


def has_perm(role: str, perm: Perm) -> bool:
    try:
        return perm in PERMISSIONS[Role(role)]
    except (KeyError, ValueError):
        return False


def can_approve(role: str) -> bool:
    return has_perm(role, Perm.DRAFT_APPROVE)
