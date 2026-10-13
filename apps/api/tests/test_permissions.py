from app.enums import Role
from app.permissions import Perm, can_approve, has_perm


def test_only_the_owner_decides():
    assert can_approve(Role.OWNER)
    assert not can_approve(Role.ASSISTANT)
    assert not can_approve(Role.SYSADMIN)
    for perm in (Perm.DRAFT_PUBLISH, Perm.DRAFT_LOWER_RISK, Perm.REDLINE_MANAGE, Perm.REPORT_RUN):
        assert has_perm(Role.OWNER, perm) and not has_perm(Role.ASSISTANT, perm), perm


def test_the_assistant_prepares_material_and_curates_sources():
    for perm in (Perm.SIGNAL_ADD, Perm.DRAFT_EDIT, Perm.SOURCES_MANAGE):
        assert has_perm(Role.ASSISTANT, perm), perm
    for perm in (Perm.DRAFT_APPROVE, Perm.USERS_MANAGE, Perm.AUDIT_VIEW):
        assert not has_perm(Role.ASSISTANT, perm), perm


def test_sysadmin_never_touches_content():
    for perm in Perm:
        if perm not in (Perm.USERS_MANAGE, Perm.AUDIT_VIEW):
            assert not has_perm(Role.SYSADMIN, perm), perm


def test_unknown_role_has_nothing():
    assert not has_perm("nonsense", Perm.SIGNAL_ADD)
    assert not can_approve("diplomatic_editor")  # a retired role grants nothing
