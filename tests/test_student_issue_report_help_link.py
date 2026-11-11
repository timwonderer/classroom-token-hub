"""Regression: the three student issue-report pages must link "Open full guide"
to the report-issues guide, not the generic Help Center.

``templates/layout_student.html`` resolves the drawer's doc link with
``current_page or request.endpoint``, and ``help_doc_map`` already has correct,
endpoint-keyed entries for all three routes pointing at
``support/report-issues``. But ``app/routes/student.py`` used to pass
``current_page='help'`` into ``render_template`` for all three routes, which
won over ``request.endpoint`` and sent "Open full guide" to the generic
``support/help-center`` entry instead.
"""

from __future__ import annotations

from decimal import Decimal

from uuid import uuid4

from app.extensions import db
from app.feats.base import FEATContext
from app.models import AttendanceSession
from tests.helpers.classroom_initializer import initialize_as_student
from tests.helpers.ledger import create_ledger_idempotent_transaction

REPORT_ISSUES_GUIDE = b"user-guides/features/student/support/report-issues"
HELP_CENTER_GUIDE = b"user-guides/features/student/support/help-center"


def test_submit_general_issue_links_to_report_issues_guide(client, app):
    initialize_as_student("chemistry_p1", client, app)

    resp = client.get("/student/help-support/submit-issue", follow_redirects=False)

    assert resp.status_code == 200
    assert REPORT_ISSUES_GUIDE in resp.data
    assert HELP_CENTER_GUIDE not in resp.data


def test_report_transaction_issue_links_to_report_issues_guide(client, app):
    classroom, student = initialize_as_student("chemistry_p1", client, app)

    with app.app_context():
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"test:help-link:{uuid4().hex}"):
            transaction, _created = create_ledger_idempotent_transaction(
                idempotency_key=f"test:help-link:{student.seat.id}:{uuid4().hex}",
                seat_id=student.seat.id,
                class_id=classroom.class_id,
                amount=Decimal("10.00"),
                account_type="checking",
                type="payroll",
                description="Test funding",
            )
        transaction_id = transaction.id

    resp = client.get(
        f"/student/help-support/transaction/{transaction_id}/report",
        follow_redirects=False,
    )

    assert resp.status_code == 200
    assert REPORT_ISSUES_GUIDE in resp.data
    assert HELP_CENTER_GUIDE not in resp.data


def test_report_attendance_session_issue_links_to_report_issues_guide(client, app):
    classroom, student = initialize_as_student("chemistry_p1", client, app)

    with app.app_context():
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"test:help-link:{uuid4().hex}"):
            session = AttendanceSession(
                target_seat_id=student.seat.id,
                class_id=classroom.class_id,
                actor_seat_id=student.seat.id,
                mechanism="self",
                status="active",
                reason_code="work",
            )
            db.session.add(session)
        session_id = session.id

    resp = client.get(
        f"/student/help-support/attendance-session/{session_id}/report",
        follow_redirects=False,
    )

    assert resp.status_code == 200
    assert REPORT_ISSUES_GUIDE in resp.data
    assert HELP_CENTER_GUIDE not in resp.data
