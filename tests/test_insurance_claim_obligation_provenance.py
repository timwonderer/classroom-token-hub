"""Obligation payments are never a TRANSACTION insurance claim basis.

FEAT-STOR-003 §A puts obligation charges in CTH's global disallowed set, and
SPEC-OPS-001 §VII decides obligation-relatedness by provenance, not
representation. The predicate used to recognise obligations by the type names
``rent`` / ``property_tax``, which the ledger never writes: rent and its late
fees post as ``rent_payment``, so a student could claim both. These tests drive
the real rent-payment FEAT, file and approve through FEAT-STOR-003, and hold
every closed-vocabulary type to a verdict.
"""

import re
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.reconcile_rent_feat import execute_reconcile_rent
from app.feats.rent_payment_feat import execute_rent_payment
from app.models import ObligationAssessment, Transaction
from app.feats.insurance_claim_feat import resolve_insurance_claim, submit_insurance_claim
from app.services import insurance_eligibility_contract as eligibility
from app.services import obligations_service
from app.services.context_resolver import CanonicalContext
from tests.helpers.class_domain import customize_rent_settings, enable_class_feature
from tests.helpers.classroom_initializer import initialize
from tests.helpers.ledger import create_ledger_idempotent_transaction
from tests.test_insurance_claim_feat import _add_granted_event

_FIRST_DUE = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
_T_INITIAL = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
_T_BEFORE_BOUNDARY = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)


def _closed_ledger_vocabulary():
    """The ledger's closed type vocabulary, read from the live CHECK constraint."""
    definition = db.session.execute(text(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conname = 'ck_ledger_transaction_type_closed_vocabulary'"
    )).scalar_one()
    return set(re.findall(r"'([^']+)'", definition))


def _admitted_types(vocabulary):
    """Types whose bare (unlinked) loss the predicate would accept as a claim basis."""
    admitted = set()
    for ttype in vocabulary:
        txn = Transaction(class_id="c1", seat_id=1, amount=Decimal("-5.00"),
                          type=ttype, correlation_id=f"corr_{uuid4().hex}")
        if eligibility.evaluate_transaction_claim_basis(
            txn, class_id="c1", covered_seat_id=1
        ).eligible:
            admitted.add(ttype)
    return admitted


def test_only_purchase_is_an_insurable_type_in_the_closed_vocabulary(app):
    with app.app_context():
        vocabulary = _closed_ledger_vocabulary()
        assert "rent_payment" in vocabulary
        assert _admitted_types(vocabulary) == {"purchase"}


def test_vocabulary_guard_catches_a_dropped_obligation_type(app, monkeypatch):
    """Mutation proof (SOP-TEST-003 §IX.A): losing the backstop is reported."""
    with app.app_context():
        monkeypatch.setattr(eligibility, "OBLIGATION_TYPES", frozenset({"rent", "property_tax"}))
        assert "rent_payment" in _admitted_types(_closed_ledger_vocabulary())


def _covered_seat_with_paid_rent_and_late_fee(app, key="chemistry_p1"):
    """A seat holding TRANSACTION insurance that then pays rent and a late fee."""
    classroom = initialize(key, app)
    student = classroom.students[0]
    seat_id = student.seat.id
    entitlement_id = str(uuid4())
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"cover:{seat_id}"):
        _add_granted_event(classroom, student, entitlement_id, reimbursement_percentage="80")
    enable_class_feature(class_id=classroom.class_id, feature="rent")
    customize_rent_settings(
        classroom.class_id, frequency_type="monthly", due_day_of_month=1,
        first_rent_due_date=_FIRST_DUE, grace_period_days=3,
        rent_amount=Decimal("50.00"), satisfaction_benefits=[],
        late_penalty_amount=Decimal("10.00"), late_penalty_type="once",
    )
    execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)
    execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_BEFORE_BOUNDARY)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"fund:{seat_id}"):
        create_ledger_idempotent_transaction(
            idempotency_key=f"fund-seat:{seat_id}", seat_id=seat_id,
            class_id=classroom.class_id, amount=Decimal("100.00"),
            account_type="checking", type="payroll", description="Test funding",
        )

    paid = {}
    for obligation_type in ("RENT", "LATE_FEE"):
        assessment = ObligationAssessment.query.filter_by(
            class_id=classroom.class_id, seat_id=seat_id,
            obligation_type=obligation_type, event_type="ASSESSMENT",
        ).first()
        result = execute_rent_payment(
            classroom.class_id, seat_id, assessment.correlation_id,
            idempotency_key=f"pay:{assessment.correlation_id}",
        )
        assert result.success is True, result.error_message
        paid[obligation_type] = db.session.get(Transaction, result.transaction_id)
    return classroom, student, entitlement_id, paid


def _student_context(classroom, student):
    return CanonicalContext(user_id=student.user.id, class_id=classroom.class_id,
                            seat_id=student.seat.id, actor_role="student")


def _teacher_context(classroom):
    teacher = classroom.teacher_seat
    return CanonicalContext(user_id=teacher.user_id, class_id=classroom.class_id,
                            seat_id=teacher.id, actor_role="teacher")


def test_rent_and_late_fee_payments_are_refused_at_submission(app):
    with app.app_context():
        classroom, student, entitlement_id, paid = _covered_seat_with_paid_rent_and_late_fee(app)
        for obligation_type, txn in paid.items():
            result = submit_insurance_claim(
                canonical_context=_student_context(classroom, student),
                entitlement_id=entitlement_id, claim_subject={"transaction_id": txn.id},
            )
            assert result.success is False, obligation_type
            assert result.error_code == "INELIGIBLE_TRANSACTION", obligation_type
            assert result.error_message.startswith(eligibility.OBLIGATION), obligation_type


def test_provenance_alone_refuses_at_submission(app, monkeypatch):
    """With the type backstop gone, the FEAT's provenance read still refuses."""
    with app.app_context():
        classroom, student, entitlement_id, paid = _covered_seat_with_paid_rent_and_late_fee(app)
        monkeypatch.setattr(eligibility, "OBLIGATION_TYPES", frozenset())
        for obligation_type, txn in paid.items():
            assert eligibility.evaluate_transaction_claim_basis(
                txn, class_id=classroom.class_id, covered_seat_id=student.seat.id
            ).eligible is True, "the Store predicate alone no longer refuses"
            result = submit_insurance_claim(
                canonical_context=_student_context(classroom, student),
                entitlement_id=entitlement_id, claim_subject={"transaction_id": txn.id},
            )
            assert result.error_message.startswith(eligibility.OBLIGATION), obligation_type


def test_provenance_alone_refuses_at_approval(app, monkeypatch):
    """A claim that reached SUBMITTED on an obligation payment cannot be approved."""
    with app.app_context():
        classroom, student, entitlement_id, paid = _covered_seat_with_paid_rent_and_late_fee(app)
        monkeypatch.setattr(eligibility, "OBLIGATION_TYPES", frozenset())
        # Let the submission through, as production did before this fix.
        with monkeypatch.context() as m:
            m.setattr(obligations_service, "is_obligation_related_transaction",
                      lambda *_a, **_k: False)
            submitted = submit_insurance_claim(
                canonical_context=_student_context(classroom, student),
                entitlement_id=entitlement_id,
                claim_subject={"transaction_id": paid["RENT"].id},
            )
        assert submitted.success is True, submitted.error_message

        result = resolve_insurance_claim(
            canonical_context=_teacher_context(classroom),
            claim_id=submitted.claim_id, approved=True,
        )
        assert result.success is False
        assert result.error_code == "INELIGIBLE_TRANSACTION"
        assert result.error_message.startswith(eligibility.OBLIGATION)


def test_provenance_is_read_within_the_claim_class(app):
    """An obligation event in another class does not speak for this class's row."""
    with app.app_context():
        first, _student, _ent, paid = _covered_seat_with_paid_rent_and_late_fee(app)
        other = initialize("ap_csp_p3", app)
        rent_id = paid["RENT"].id
        assert obligations_service.is_obligation_related_transaction(
            rent_id, class_id=first.class_id) is True
        assert obligations_service.is_obligation_related_transaction(
            rent_id, class_id=other.class_id) is False


def test_claim_picker_drops_obligation_payments_by_provenance(app, monkeypatch):
    from app.routes.student import _eligible_claim_transactions

    with app.app_context():
        classroom, student, entitlement_id, paid = _covered_seat_with_paid_rent_and_late_fee(app)
        seat_id = student.seat.id
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"control:{seat_id}"):
            control, _ = create_ledger_idempotent_transaction(
                idempotency_key=f"picker-control:{seat_id}", seat_id=seat_id,
                class_id=classroom.class_id, amount=Decimal("-5.00"),
                account_type="checking", type="purchase", description="Unlinked purchase",
                actor_seat_id=seat_id,
            )
        monkeypatch.setattr(eligibility, "OBLIGATION_TYPES", frozenset())
        offered = {t.id for t in _eligible_claim_transactions(
            seat_id, classroom.class_id, entitlement_id)}
        assert control.id in offered
        assert not offered & {t.id for t in paid.values()}
