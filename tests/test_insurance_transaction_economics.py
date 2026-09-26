"""Regression tests: TRANSACTION insurance economics + gates (Step 6).

Pins the four locked rules against the frozen contract and immutable claim
history — never the live policy:

1. Period payout ceiling CLAMPS (never rejects) an over-cap reimbursement;
   only APPROVED monetary payouts consume capacity; zero remaining capacity
   fails as CLAIM_ALLOWANCE_EXHAUSTED rather than a $0 approval.
2. Claim-per-week-equivalent allowance counts EVERY created lifecycle
   (SUBMITTED + APPROVED + REJECTED), is enforced at submission, and a later
   submission never retroactively denies an earlier claim's resolution.
3. Claim window is class-local calendar days from the source transaction date;
   a transaction on class-local date D with window N is filable through the end
   of D+N (inclusive) and rejected at D+N+1.

Uses the canonical test initializer per SPEC-TEST-001 and injects reference
times through the source transaction timestamp per SPEC-TIME-001 (no wall-clock
business decisions in the assertions).
"""

from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from app.extensions import db
from app.feats.base import FEATContext
from app.models import EntitlementEvent
from app.services import insurance_definition_service as insurance_defs
from app.services.context_resolver import CanonicalContext
from app.feats.insurance_claim_feat import (
    submit_insurance_claim,
    resolve_insurance_claim,
    describe_claim_contract,
)
from app.utils import canonical_temporal_resolver as canonical_temporal_resolver_module
from app.utils.canonical_temporal_resolver import (
    canonical_temporal_resolver,
    CLASS_LEVEL_EVALUATION,
    ensure_utc,
)
from tests.helpers.ledger import create_ledger_idempotent_transaction
from tests.helpers.classroom_initializer import initialize
from tests.helpers.insurance_domain import establish_paid_premium_lineage


def _frozen(
    *,
    premium="100.00",
    payout_multiple="1",
    reimbursement_percentage="100",
    claims_per_week_equivalent="5",
    claim_window_days=7,
) -> dict:
    return {
        "insurance_type": "TRANSACTION",
        "premium": premium,
        "charge_frequency": "WEEKLY", "bill_preview_days": 3, "nonpayment_mode": "ACCUMULATE",
        "reimbursement_percentage": reimbursement_percentage,
        "payout_multiple": payout_multiple,
        "claims_per_week_equivalent": claims_per_week_equivalent,
        "claim_window_days": claim_window_days,
    }


def _add_granted(classroom, student, entitlement_id, *, granted_at=None, **frozen_kwargs):
    # Claim-time authority is the IMMUTABLE ``insurance_policies`` row resolved via
    # the GRANTED entitlement's ``policy_uuid`` — never a ``frozen_contract`` payload
    # snapshot (FEAT-STOR-003 §1.2, DOM-STORE-001 §VII.A). A policy edit mints a new
    # ``policy_uuid``, so the referenced row IS the frozen contract. The entitlement
    # payload therefore duplicates no terms; it carries only the ``policy_uuid``
    # reference, exactly like ``grant_insurance_entitlement``.
    definition = dict(_frozen(**frozen_kwargs))
    definition["title"] = "Insurance Policy"
    policy = insurance_defs.create_insurance_definition(
        class_id=classroom.class_id,
        actor_seat_id=classroom.teacher_seat.id,
        definition=definition,
    )
    ev = EntitlementEvent(
        event_id=str(uuid4()),
        class_id=classroom.class_id,
        entitlement_id=entitlement_id,
        target_seat_id=student.seat.id,
        actor_seat_id=student.seat.id,
        product_id=None,
        entitlement_type="INSURANCE",
        acquisition_type="PURCHASE",
        event_type="GRANTED",
        payload={"policy_uuid": policy.policy_uuid},
    )
    if granted_at is not None:
        ev.timestamp = granted_at
    db.session.add(ev)
    db.session.flush()
    # A real purchase gives the entitlement a paid premium lineage; without one
    # it has no coverage period and is not usable (DOM-STORE-001 §VIII.E.1).
    establish_paid_premium_lineage(
        class_id=classroom.class_id, seat_id=student.seat.id,
        entitlement_id=entitlement_id, policy_uuid=policy.policy_uuid,
        start_utc=ev.timestamp,
    )
    return ev


@contextmanager
def _clock_at(at):
    """Run the block as if the wall clock read ``at``.

    `Transaction.timestamp` defaults to `utc_now()`, and the Ledger posting
    boundary accepts no caller-supplied time on purpose — when a monetary effect
    happened is a fact the Ledger stamps, not a parameter a caller chooses. So a
    test that needs a loss dated eight days ago has exactly two levers: rewrite
    the row afterwards, or move the clock the insert reads.

    This used to rewrite the row, with a raw `UPDATE` chosen specifically to slip
    past the `before_update` mapper listener. That worked only because the guard
    was ORM-deep; `ledger_transaction_no_rewrite` now enforces INV-LED-002 in the
    database, where the write actually lands, and it rejects the rewrite from any
    access path. Which is the correct outcome: the fixture was not exercising a
    lawful ledger operation, it was demonstrating that the guard could be walked
    around.

    Moving the clock keeps the fiction where it belongs — in the test's notion of
    "now" — and leaves the row immutable from the moment it is inserted. The
    patch targets the `datetime` name inside the temporal resolver rather than
    `utc_now` itself, because `db.Column(default=utc_now)` captured the function
    object at class-definition time and never re-reads the module attribute.
    """
    real_datetime = canonical_temporal_resolver_module.datetime

    class _FrozenDatetime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return at if tz is not None else at.replace(tzinfo=None)

    canonical_temporal_resolver_module.datetime = _FrozenDatetime
    try:
        yield
    finally:
        canonical_temporal_resolver_module.datetime = real_datetime


def _seed_loss(classroom, student, *, idem, amount, at=None):
    def _create():
        txn, _created = create_ledger_idempotent_transaction(
            idempotency_key=f"econ-source:{idem}:{uuid4().hex}",
            seat_id=student.seat.id,
            class_id=classroom.class_id,
            amount=Decimal(amount),
            account_type="checking",
            type="purchase",
            description="Insurance claim source loss",
            actor_seat_id=student.seat.id,
        )
        return txn

    if at is None:
        return _create()
    with _clock_at(at):
        return _create()


def _student_ctx(classroom, student):
    return CanonicalContext(
        user_id=student.user.id,
        class_id=classroom.class_id,
        seat_id=student.seat.id,
        actor_role="student",
    )


def _teacher_ctx(classroom):
    t = classroom.teacher_seat
    return CanonicalContext(
        user_id=t.user_id,
        class_id=classroom.class_id,
        seat_id=t.id,
        actor_role="teacher",
    )


def _now_utc(classroom, student):
    temporal = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=_student_ctx(classroom, student),
        primitive="current_time",
    )
    return ensure_utc(temporal.canonical_now_utc)


class TestPeriodPayoutCeiling:
    def test_second_approval_clamps_to_remaining_capacity_then_exhausts(self, app):
        """Ceiling = premium × payout_multiple = 10.00. Two 8.00 losses at 100%:
        first pays 8.00, second CLAMPS to the remaining 2.00, and a third
        submission fails CLAIM_ALLOWANCE_EXHAUSTED (capacity, not nominal, rules)."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="econ-clamp"):
                _add_granted(
                    classroom, student, entitlement_id,
                    premium="10.00", payout_multiple="1",
                    reimbursement_percentage="100", claims_per_week_equivalent="5",
                )
                loss1 = _seed_loss(classroom, student, idem="clamp-1", amount="-8.00").id
                loss2 = _seed_loss(classroom, student, idem="clamp-2", amount="-8.00").id
                loss3 = _seed_loss(classroom, student, idem="clamp-3", amount="-8.00").id

            student_ctx = _student_ctx(classroom, student)
            teacher_ctx = _teacher_ctx(classroom)

            # Claim 1: full 8.00.
            s1 = submit_insurance_claim(
                canonical_context=student_ctx, entitlement_id=entitlement_id,
                claim_subject={"transaction_id": loss1}, correlation_id=f"corr_{uuid4().hex}",
            )
            assert s1.success is True, s1.error_message
            r1 = resolve_insurance_claim(
                canonical_context=teacher_ctx, claim_id=s1.claim_id, approved=True
            )
            assert r1.success is True, r1.error_message
            assert r1.reimbursement_amount == Decimal("8.00")

            # Claim 2: nominal 8.00 but only 2.00 capacity remains → CLAMPED to 2.00.
            s2 = submit_insurance_claim(
                canonical_context=student_ctx, entitlement_id=entitlement_id,
                claim_subject={"transaction_id": loss2}, correlation_id=f"corr_{uuid4().hex}",
            )
            assert s2.success is True, s2.error_message
            r2 = resolve_insurance_claim(
                canonical_context=teacher_ctx, claim_id=s2.claim_id, approved=True
            )
            assert r2.success is True, r2.error_message
            assert r2.reimbursement_amount == Decimal("2.00")

            # Capacity is now exhausted (8 + 2 == 10). A third submission fails.
            s3 = submit_insurance_claim(
                canonical_context=student_ctx, entitlement_id=entitlement_id,
                claim_subject={"transaction_id": loss3}, correlation_id=f"corr_{uuid4().hex}",
            )
            assert s3.success is False
            assert s3.error_code == "CLAIM_ALLOWANCE_EXHAUSTED"

    def test_rejected_claims_do_not_consume_payout_capacity(self, app):
        """Only APPROVED monetary results consume the payout ceiling."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="econ-reject-nocap"):
                _add_granted(
                    classroom, student, entitlement_id,
                    premium="10.00", payout_multiple="1",
                    reimbursement_percentage="100", claims_per_week_equivalent="5",
                )
                loss1 = _seed_loss(classroom, student, idem="rc-1", amount="-10.00").id
                loss2 = _seed_loss(classroom, student, idem="rc-2", amount="-10.00").id

            student_ctx = _student_ctx(classroom, student)
            teacher_ctx = _teacher_ctx(classroom)

            s1 = submit_insurance_claim(
                canonical_context=student_ctx, entitlement_id=entitlement_id,
                claim_subject={"transaction_id": loss1}, correlation_id=f"corr_{uuid4().hex}",
            )
            assert s1.success is True, s1.error_message
            r1 = resolve_insurance_claim(
                canonical_context=teacher_ctx, claim_id=s1.claim_id, approved=False
            )
            assert r1.success is True and r1.decision == "REJECTED"

            # The rejected claim consumed no capacity, so the full 10.00 pays out.
            s2 = submit_insurance_claim(
                canonical_context=student_ctx, entitlement_id=entitlement_id,
                claim_subject={"transaction_id": loss2}, correlation_id=f"corr_{uuid4().hex}",
            )
            assert s2.success is True, s2.error_message
            r2 = resolve_insurance_claim(
                canonical_context=teacher_ctx, claim_id=s2.claim_id, approved=True
            )
            assert r2.success is True, r2.error_message
            assert r2.reimbursement_amount == Decimal("10.00")


class TestClaimAllowance:
    def test_rejected_claim_counts_and_limit_is_enforced_at_submission(self, app):
        """Allowance = ceil(2 × 1) = 2. A rejected claim still counts; the third
        submission is blocked; and resolving the second claim afterward still
        APPROVES (a later submission never retroactively denies it)."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            entitlement_id = str(uuid4())
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="econ-allowance"):
                _add_granted(
                    classroom, student, entitlement_id,
                    premium="100.00", payout_multiple="1",
                    reimbursement_percentage="100", claims_per_week_equivalent="2",
                )
                loss1 = _seed_loss(classroom, student, idem="al-1", amount="-5.00").id
                loss2 = _seed_loss(classroom, student, idem="al-2", amount="-5.00").id
                loss3 = _seed_loss(classroom, student, idem="al-3", amount="-5.00").id

            student_ctx = _student_ctx(classroom, student)
            teacher_ctx = _teacher_ctx(classroom)

            # Claim 1 created, then REJECTED — it still consumes one allowance slot.
            s1 = submit_insurance_claim(
                canonical_context=student_ctx, entitlement_id=entitlement_id,
                claim_subject={"transaction_id": loss1}, correlation_id=f"corr_{uuid4().hex}",
            )
            assert s1.success is True, s1.error_message
            rej = resolve_insurance_claim(
                canonical_context=teacher_ctx, claim_id=s1.claim_id, approved=False
            )
            assert rej.success is True and rej.decision == "REJECTED"

            # Claim 2 created — allowance now fully consumed (rejected + this one).
            s2 = submit_insurance_claim(
                canonical_context=student_ctx, entitlement_id=entitlement_id,
                claim_subject={"transaction_id": loss2}, correlation_id=f"corr_{uuid4().hex}",
            )
            assert s2.success is True, s2.error_message

            # Claim 3 is blocked at SUBMISSION by the per-period allowance.
            s3 = submit_insurance_claim(
                canonical_context=student_ctx, entitlement_id=entitlement_id,
                claim_subject={"transaction_id": loss3}, correlation_id=f"corr_{uuid4().hex}",
            )
            assert s3.success is False
            assert s3.error_code == "CLAIM_LIMIT_EXCEEDED"

            # Resolution of claim 2 is NOT retroactively denied by the later attempt.
            r2 = resolve_insurance_claim(
                canonical_context=teacher_ctx, claim_id=s2.claim_id, approved=True
            )
            assert r2.success is True, r2.error_message
            assert r2.decision == "APPROVED"
            assert r2.reimbursement_amount == Decimal("5.00")


class TestClaimWindow:
    def test_transaction_on_last_eligible_day_is_timely(self, app):
        """A transaction whose class-local date is exactly window_days ago (D where
        D + N == today) may still be filed today."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            now_utc = _now_utc(classroom, student)
            entitlement_id = str(uuid4())
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="econ-window-ok"):
                _add_granted(
                    classroom, student, entitlement_id,
                    claim_window_days=7, claims_per_week_equivalent="5",
                    premium="100.00", payout_multiple="1",
                    granted_at=now_utc - timedelta(days=30),
                )
                loss = _seed_loss(
                    classroom, student, idem="win-ok", amount="-5.00",
                    at=now_utc - timedelta(days=7),
                ).id

            s = submit_insurance_claim(
                canonical_context=_student_ctx(classroom, student),
                entitlement_id=entitlement_id,
                claim_subject={"transaction_id": loss},
                correlation_id=f"corr_{uuid4().hex}",
            )
            assert s.success is True, s.error_message

    def test_transaction_past_window_is_still_submittable(self, app):
        """One class-local day past the window (D + N < today) still files.

        Operator decision 2026-09-21: the filing window is a soft,
        teacher-overridable gate at APPROVAL, not a submission-time rejection —
        see TestFilingWindowApprovalGate below. A student who files late must
        still be able to reach a teacher for review.
        """
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        with app.app_context():
            now_utc = _now_utc(classroom, student)
            entitlement_id = str(uuid4())
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="econ-window-late"):
                _add_granted(
                    classroom, student, entitlement_id,
                    claim_window_days=7, claims_per_week_equivalent="5",
                    premium="100.00", payout_multiple="1",
                    granted_at=now_utc - timedelta(days=30),
                )
                loss = _seed_loss(
                    classroom, student, idem="win-late", amount="-5.00",
                    at=now_utc - timedelta(days=8),
                ).id

            s = submit_insurance_claim(
                canonical_context=_student_ctx(classroom, student),
                entitlement_id=entitlement_id,
                claim_subject={"transaction_id": loss},
                correlation_id=f"corr_{uuid4().hex}",
            )
            assert s.success is True, s.error_message

    def test_filed_within_window_reflects_lateness(self, app):
        """``describe_claim_contract().filed_within_window`` is the single source
        the review screen and the approval gate both read -- prove it actually
        distinguishes the two cases rather than always reporting one value."""
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        with app.app_context():
            now_utc = _now_utc(classroom, student)

            on_time_id = str(uuid4())
            late_id = str(uuid4())
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="econ-window-projection"):
                _add_granted(
                    classroom, student, on_time_id,
                    claim_window_days=7, claims_per_week_equivalent="5",
                    premium="100.00", payout_multiple="1",
                    granted_at=now_utc - timedelta(days=30),
                )
                on_time_loss = _seed_loss(
                    classroom, student, idem="win-proj-ontime", amount="-5.00",
                    at=now_utc - timedelta(days=1),
                ).id
                _add_granted(
                    classroom, student, late_id,
                    claim_window_days=7, claims_per_week_equivalent="5",
                    premium="100.00", payout_multiple="1",
                    granted_at=now_utc - timedelta(days=30),
                )
                late_loss = _seed_loss(
                    classroom, student, idem="win-proj-late", amount="-5.00",
                    at=now_utc - timedelta(days=8),
                ).id

            s_on_time = submit_insurance_claim(
                canonical_context=_student_ctx(classroom, student),
                entitlement_id=on_time_id,
                claim_subject={"transaction_id": on_time_loss},
                correlation_id=f"corr_{uuid4().hex}",
            )
            s_late = submit_insurance_claim(
                canonical_context=_student_ctx(classroom, student),
                entitlement_id=late_id,
                claim_subject={"transaction_id": late_loss},
                correlation_id=f"corr_{uuid4().hex}",
            )
            assert s_on_time.success is True, s_on_time.error_message
            assert s_late.success is True, s_late.error_message

            from app.models import InsuranceClaim

            on_time_claim = db.session.query(InsuranceClaim).filter_by(
                claim_id=s_on_time.claim_id
            ).one()
            late_claim = db.session.query(InsuranceClaim).filter_by(
                claim_id=s_late.claim_id
            ).one()

            on_time_contract = describe_claim_contract(
                on_time_claim, canonical_context=_teacher_ctx(classroom)
            )
            late_contract = describe_claim_contract(
                late_claim, canonical_context=_teacher_ctx(classroom)
            )
            assert on_time_contract.filed_within_window is True
            assert late_contract.filed_within_window is False


class TestFilingWindowApprovalGate:
    """A late TRANSACTION claim reaches SUBMITTED; approving it needs a reason.

    Restores a mechanism dropped in the 2026-08-28 insurance rewrite (present
    pre-rewrite as ``time_limit_override_reason``, main_legacy_v1.10.0). Unlike
    v1 -- which hard-blocked approval and clamped the payout on other gates --
    here the filing window is the ONE soft gate: approval is blocked only
    until a written reason is recorded, then proceeds normally. Rejection
    never needs a reason; a late claim is not otherwise invalid.
    """

    def _late_claim(self, app, classroom, student):
        now_utc = _now_utc(classroom, student)
        entitlement_id = str(uuid4())
        with FEATContext("FEAT-TEST-SETUP", idempotency_key="econ-window-gate"):
            _add_granted(
                classroom, student, entitlement_id,
                claim_window_days=7, claims_per_week_equivalent="5",
                premium="100.00", payout_multiple="1",
                granted_at=now_utc - timedelta(days=30),
            )
            loss = _seed_loss(
                classroom, student, idem="win-gate", amount="-5.00",
                at=now_utc - timedelta(days=8),
            ).id
        s = submit_insurance_claim(
            canonical_context=_student_ctx(classroom, student),
            entitlement_id=entitlement_id,
            claim_subject={"transaction_id": loss},
            correlation_id=f"corr_{uuid4().hex}",
        )
        assert s.success is True, s.error_message
        return s.claim_id

    def test_approval_without_a_reason_is_refused(self, app):
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        with app.app_context():
            claim_id = self._late_claim(app, classroom, student)
            r = resolve_insurance_claim(
                canonical_context=_teacher_ctx(classroom),
                claim_id=claim_id,
                approved=True,
            )
            assert r.success is False
            assert r.error_code == "FILING_WINDOW_OVERRIDE_REQUIRED"

            from app.services import insurance_claim_service
            claim = insurance_claim_service.get_claim(claim_id, class_id=classroom.class_id)
            assert claim.status == insurance_claim_service.SUBMITTED, (
                "a refused approval must not silently leave the claim decided"
            )

    def test_approval_with_a_reason_succeeds_and_is_recorded(self, app):
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        with app.app_context():
            claim_id = self._late_claim(app, classroom, student)
            r = resolve_insurance_claim(
                canonical_context=_teacher_ctx(classroom),
                claim_id=claim_id,
                approved=True,
                filing_window_override_reason="Family emergency verified with front office.",
            )
            assert r.success is True, r.error_message
            assert r.decision == "APPROVED"

            from app.services import insurance_claim_service
            claim = insurance_claim_service.get_claim(claim_id, class_id=classroom.class_id)
            assert claim.status == insurance_claim_service.APPROVED
            assert claim.filing_window_override_reason == (
                "Family emergency verified with front office."
            )

    def test_rejection_of_a_late_claim_needs_no_reason(self, app):
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        with app.app_context():
            claim_id = self._late_claim(app, classroom, student)
            r = resolve_insurance_claim(
                canonical_context=_teacher_ctx(classroom),
                claim_id=claim_id,
                approved=False,
            )
            assert r.success is True, r.error_message
            assert r.decision == "REJECTED"

    def test_claim_within_window_needs_no_reason_to_approve(self, app):
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]
        with app.app_context():
            now_utc = _now_utc(classroom, student)
            entitlement_id = str(uuid4())
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="econ-window-ontime"):
                _add_granted(
                    classroom, student, entitlement_id,
                    claim_window_days=7, claims_per_week_equivalent="5",
                    premium="100.00", payout_multiple="1",
                    granted_at=now_utc - timedelta(days=30),
                )
                loss = _seed_loss(
                    classroom, student, idem="win-ontime", amount="-5.00",
                    at=now_utc - timedelta(days=1),
                ).id
            s = submit_insurance_claim(
                canonical_context=_student_ctx(classroom, student),
                entitlement_id=entitlement_id,
                claim_subject={"transaction_id": loss},
                correlation_id=f"corr_{uuid4().hex}",
            )
            assert s.success is True, s.error_message

            r = resolve_insurance_claim(
                canonical_context=_teacher_ctx(classroom),
                claim_id=s.claim_id,
                approved=True,
            )
            assert r.success is True, r.error_message
