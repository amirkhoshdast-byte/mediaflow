import pytest

from app.enums import Role
from app.permissions import Perm, can_approve, has_perm


@pytest.mark.parametrize("risk", ["low", "medium"])
def test_low_medium_approved_by_editor_and_office(risk):
    assert can_approve(Role.DIPLOMATIC_EDITOR, risk)
    assert can_approve(Role.PRESIDENT_OFFICE, risk)


@pytest.mark.parametrize("risk", ["high", "critical"])
def test_high_critical_only_president_office(risk):
    assert can_approve(Role.PRESIDENT_OFFICE, risk)
    for role in Role:
        if role != Role.PRESIDENT_OFFICE:
            assert not can_approve(role, risk), role


def test_sysadmin_never_approves_content():
    for risk in ["low", "medium", "high", "critical"]:
        assert not can_approve(Role.SYSADMIN, risk)
    assert not has_perm(Role.SYSADMIN, Perm.DRAFT_EDIT)


def test_only_content_lead_submits_for_review():
    assert [r for r in Role if has_perm(r, Perm.DRAFT_SUBMIT)] == [Role.CONTENT_LEAD]


def test_unknown_role_has_nothing():
    assert not has_perm("nonsense", Perm.SIGNAL_ADD)
