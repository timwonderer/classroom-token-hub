"""Reporting an issue on a transaction must find the transaction.

The lookup scoped by ``ledger_transaction.join_code``, a nullable legacy column
the FEAT ledger writer never populates. Every row therefore failed the filter
and ``first_or_404`` answered 404 for transactions the student plainly owns.
``class_id`` is the canonical isolation key -- see .claude/rules/multi-tenancy.md.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from tests.helpers.canonical_classroom import login_student, provision_classroom
from tests.helpers.ledger import create_ledger_idempotent_transaction

pytestmark = [pytest.mark.regression]


def test_report_transaction_issue_page_resolves_the_students_transaction(client, app):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        student = classroom.students[0]
        class_id = classroom.class_id

        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"report:fund:{student.seat_id}"):
            txn, _created = create_ledger_idempotent_transaction(
                idempotency_key=f"report-fund:{student.seat_id}",
                seat_id=student.seat_id,
                class_id=class_id,
                amount=Decimal("25.00"),
                account_type="checking",
                type="payroll",
                description="Transaction report test funding",
            )
        db.session.commit()
        transaction_id = txn.id

        login_student(client, student)

    response = client.get(f"/student/help-support/transaction/{transaction_id}/report")

    assert response.status_code == 200, response.status_code
