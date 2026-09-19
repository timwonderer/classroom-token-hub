"""Payroll policy provenance follows the authority that decided the amount (DOM-PROD-001 §VIII).

Attendance-derived payroll is priced under a payroll policy version and must
record it. A teacher's manual credit is an amount the teacher chose, so a class
with no payroll configuration can still pay students manually. A manual_credit
posted for another domain's lawful calculation (productivity insurance) may still
carry the policy provenance that calculation used: the rule is a minimum for
payroll, never "manual credits have no policy".
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.prod import record_payroll_event
from app.models import PayrollEvent, PolicyVersion, Transaction
from app.services.context_resolver import CanonicalContext
from app.services.payroll_settings_service import upsert_payroll_settings
from tests.helpers.class_domain import manual_payroll
from tests.helpers.classroom_initializer import initialize_as_teacher


def _ctx(classroom):
    return CanonicalContext(user_id=classroom.teacher_user.id, class_id=classroom.class_id,
                            seat_id=classroom.teacher_seat.id, actor_role="teacher")


def test_manual_payment_works_in_a_class_without_payroll_setup(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    assert PolicyVersion.query.filter_by(class_id=classroom.class_id, domain="payroll").count() == 0
    seat = classroom.students[0].seat

    response = manual_payroll(client, student_ids=[seat.public_id], description="Helped clean up", amount="12.50")

    assert response.status_code == 302
    event = PayrollEvent.query.filter_by(class_id=classroom.class_id, target_seat_id=seat.id,
                                         payroll_event_type="manual_credit").one()
    assert event.policy_version_id is None and event.policy_uuid is None
    credit = Transaction.query.filter_by(class_id=classroom.class_id, seat_id=seat.id, type="manual_payment").one()
    assert credit.amount == Decimal("12.50")


def test_payroll_event_without_policy_version_is_rejected(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with pytest.raises(ValueError, match="policy_version_id"):
        record_payroll_event(ctx=_ctx(classroom), target_seat_id=classroom.students[0].seat.id,
                             payroll_event_type="payroll", correlation_id="corr-no-policy",
                             idempotency_key="payroll:no-policy", policy_version_id=None,
                             mechanism="TEACHER", amount=Decimal("1.00"))
    db.session.rollback()


def test_database_requires_policy_provenance_for_payroll_events(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with pytest.raises(IntegrityError, match="ck_payroll_event_payroll_policy"):
        with FEATContext("FEAT-TEST-SETUP", idempotency_key="payroll:constraint"):
            db.session.add(PayrollEvent(
                class_id=classroom.class_id, actor_seat_id=classroom.teacher_seat.id,
                target_seat_id=classroom.students[0].seat.id, correlation_id="corr-constraint",
                idempotency_key="payroll:constraint", payroll_event_type="payroll", summary_json={},
            ))
            db.session.flush()
    db.session.rollback()


def test_manual_credit_may_keep_policy_provenance_from_a_calculation(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="payroll:provenance-policy"):
        upsert_payroll_settings(class_id=classroom.class_id, settings_data={"pay_rate": 0.25})
        db.session.flush()
    version = (PolicyVersion.query.filter_by(class_id=classroom.class_id, domain="payroll", is_active=True)
               .order_by(PolicyVersion.id.desc()).first())
    assert version is not None
    result = record_payroll_event(
        ctx=_ctx(classroom), target_seat_id=classroom.students[0].seat.id,
        payroll_event_type="manual_credit", correlation_id="corr-insurance-like",
        idempotency_key="payroll:insurance-like", policy_version_id=version.id,
        mechanism="system", amount=Decimal("4.00"),
        summary_json={"description": "Policy-derived reimbursement"},
    )
    assert result.payroll_event.policy_version_id == version.id
    assert result.payroll_event.policy_uuid == version.policy_uuid
