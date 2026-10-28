"""System support resolves an escalated ticket and moves no money.

The sysadmin bug reward was retired until badges are implemented (owner
ruling 2026-10-27). Removing the checkbox alone left the resolve route still
honouring `eligible_for_reward` / `reward_amount`, so a hand-built POST could
still credit a student; the route itself must ignore them.
"""
from app.extensions import db
from app.models import Issue, IssueResolutionAction, Transaction
from app.utils.opaque_refs import make_opaque_ref
from tests.dom.interpretation.helpers import (
    create_sysadmin,
    login_sysadmin,
    sysadmin_escalated_issue_state,
)


def test_DOM_SUP_001__resolving_an_escalated_issue_returns_it_to_the_teacher(client, app):
    _classroom, _student, issue = sysadmin_escalated_issue_state(client, app)
    sysadmin = create_sysadmin(username="sysadmin_issue_resolution")
    login_sysadmin(client, "sysadmin_issue_resolution", sysadmin.id)

    response = client.post(
        f"/sysadmin/issues/{make_opaque_ref('issue', issue.id)}/resolve",
        data={"resolution_note": "Confirmed and fixed."},
    )

    assert response.status_code == 302
    db.session.refresh(issue)
    assert issue.status == Issue.STATUS_DEV_RESOLVED
    assert issue.sysadmin_notes == "Confirmed and fixed."
    assert issue.sysadmin_resolved_at is not None


def test_DOM_SUP_001__resolve_ignores_retired_bug_reward_fields(client, app):
    classroom, student, issue = sysadmin_escalated_issue_state(client, app)
    sysadmin = create_sysadmin(username="sysadmin_issue_no_reward")
    login_sysadmin(client, "sysadmin_issue_no_reward", sysadmin.id)

    response = client.post(
        f"/sysadmin/issues/{make_opaque_ref('issue', issue.id)}/resolve",
        data={"resolution_note": "Confirmed and fixed.",
              "eligible_for_reward": "on", "reward_amount": "4.50"},
    )

    assert response.status_code == 302
    db.session.refresh(issue)
    assert issue.status == Issue.STATUS_DEV_RESOLVED
    assert issue.eligible_for_reward is False
    assert Transaction.query.filter_by(
        seat_id=student.seat.id, class_id=classroom.class_id, type="bug_reward").count() == 0
    assert IssueResolutionAction.query.filter_by(issue_id=issue.id).count() == 0
