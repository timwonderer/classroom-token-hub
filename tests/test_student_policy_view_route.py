"""Student policy detail view — coverage start and purchase date are derived facts.

Both values used to be fabricated: ``purchase_date`` was ``utc_now()`` (so a policy
bought yesterday reported today, rendered in UTC rather than class-local time) and
``coverage_start_date`` was read off an ObligationAssessment column that belongs to
the rent-waiver domain, so it was always NULL and every policy — including one with
a zero-day wait — rendered as "In waiting period".
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.class_configuration import configure_insurance_definition
from app.feats.purchase_insurance_feat import execute_purchase_insurance
from app.services.context_resolver import CanonicalContext
from app.utils.canonical_temporal_resolver import utc_now
from app.utils.transaction_idempotency import create_idempotent_transaction
from tests.helpers.canonical_classroom import provision_classroom, login_student
from tests.helpers.class_domain import enable_class_feature


def _teacher_ctx(classroom):
    return CanonicalContext(
        user_id=classroom.teacher_user.id, class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id, actor_role="teacher",
    )


def _student_ctx(classroom, student):
    return CanonicalContext(
        user_id=student.user.id, class_id=classroom.class_id,
        seat_id=student.seat.id, actor_role="student",
    )


def _make_non_monetary_policy(classroom, *, waiting_period_days, title):
    row = configure_insurance_definition(
        class_id=classroom.class_id,
        submission=dict(
            insurance_type="NON_MONETARY", premium="10.00", charge_frequency="WEEKLY",
            claims_per_week_equivalent="2",
            waiting_period_days=str(waiting_period_days), title=title,
        ),
        canonical_context=_teacher_ctx(classroom),
        correlation_id=f"corr_{uuid4().hex}", idempotency_key=f"cfg:{uuid4().hex}",
    )
    return row.policy_uuid


def _fund(seat, amount="100.00"):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"fund:{seat.id}:{uuid4().hex}"):
        create_idempotent_transaction(
            idempotency_key=f"fund:{seat.id}:{uuid4().hex}",
            seat_id=seat.id, class_id=seat.class_id, target_seat_id=seat.id,
            actor_seat_id=seat.id, mechanism="self", user_id=seat.user_id,
            amount=Decimal(amount), account_type="checking", type="payroll",
            description="test funding",
        )
    db.session.commit()


def _buy(classroom, student, policy_uuid):
    execute_purchase_insurance(
        canonical_context=_student_ctx(classroom, student),
        policy_uuid=policy_uuid, idempotency_key=f"ins:{uuid4().hex}",
    )
    db.session.commit()


def test_zero_day_waiting_period_is_not_in_waiting_period(app, client):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        enable_class_feature(class_id=classroom.class_id, feature="insurance")
        policy_uuid = _make_non_monetary_policy(
            classroom, waiting_period_days=0, title="Immediate Cover")
        student = classroom.students[0]
        _fund(student.seat)
        _buy(classroom, student, policy_uuid)
        login_student(client, student)

    resp = client.get(f"/student/insurance/policy/{policy_uuid}")
    assert resp.status_code == 200
    assert b"0-day waiting period" not in resp.data
    assert b"File a Claim (Waiting Period)" not in resp.data


def test_nonzero_waiting_period_reports_the_effective_start_date(app, client):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        enable_class_feature(class_id=classroom.class_id, feature="insurance")
        policy_uuid = _make_non_monetary_policy(
            classroom, waiting_period_days=3, title="Delayed Cover")
        student = classroom.students[0]
        _fund(student.seat)
        _buy(classroom, student, policy_uuid)
        login_student(client, student)

    resp = client.get(f"/student/insurance/policy/{policy_uuid}")
    assert resp.status_code == 200
    assert b"3-day waiting period" in resp.data
    assert b"Waiting Period" in resp.data  # claim action stays disabled


def test_purchase_date_is_the_grant_date_not_now(app, client):
    from app.utils.temporal_display import format_date, resolve_display_timezone

    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        enable_class_feature(class_id=classroom.class_id, feature="insurance")
        policy_uuid = _make_non_monetary_policy(
            classroom, waiting_period_days=0, title="Immediate Cover")
        student = classroom.students[0]
        _fund(student.seat)
        _buy(classroom, student, policy_uuid)

        # Backdate the grant: the page must report when coverage was bought, not now.
        from sqlalchemy import update
        from app.models import EntitlementEvent
        purchased_at = utc_now() - timedelta(days=5)
        db.session.execute(
            update(EntitlementEvent)
            .where(EntitlementEvent.class_id == classroom.class_id,
                   EntitlementEvent.target_seat_id == student.seat.id,
                   EntitlementEvent.entitlement_type == "INSURANCE")
            .values(timestamp=purchased_at)
        )
        db.session.commit()

        expected = format_date(
            purchased_at,
            resolve_display_timezone(_student_ctx(classroom, student)),
        )
        login_student(client, student)

    resp = client.get(f"/student/insurance/policy/{policy_uuid}")
    assert resp.status_code == 200
    assert expected.encode() in resp.data
