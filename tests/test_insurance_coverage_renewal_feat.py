"""FEAT-STOR-007 — insurance coverage renewal, usability, nonpayment, claims.

Holds the ratified rules (DOM-STORE-001 §VIII.C/§VIII.E.1, DOM-OBL-001 §V.7/§V.8,
FEAT-STOR-007, FEAT-STOR-003 §IV/§XII):

- advance premium + automatic payment → uninterrupted rollover;
- an unpaid premium gates the new period; a failed autopay is recoverable by a
  manual payment before or after the boundary; restoration is prospective only;
- ACCUMULATE keeps assessing; paying only the newest premium restores nothing
  while an older one is outstanding;
- CANCEL_AFTER_X_DAYS expires the entitlement (EXPIRED, nonpayment cause) at the
  deadline — X may exceed one period — terminates the lineage there, withdraws
  an untouched advance premium for a later period (even when the job runs
  late), keeps pre-termination debt, and a late payment resurrects nothing;
- stop-renewal during the preview: unpaid → withdrawn, coverage ends at the
  current period's end; any payment → the period is committed and runs out;
- claims: eligibility fixed at filing; allowance per coverage period;
- monthly anchored roll-forward boundaries from a purchase on the 31st.

The tests drive a controlled clock: the resolver's ``datetime`` is patched (as
tests/test_insurance_transaction_economics.py does), so both canonical "now"
and every event timestamp read the test's time. chemistry_p1 is
America/Los_Angeles; ``local()`` converts class-local wall times to UTC.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import pytz

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.cancel_insurance_feat import execute_cancel_insurance
from app.feats.class_configuration import configure_insurance_definition
from app.feats.insurance_claim_feat import resolve_insurance_claim, submit_insurance_claim
from app.feats.insurance_coverage_renewal_feat import (
    execute_insurance_coverage_renewal,
    premium_correlation_id,
)
from app.feats.insurance_premium_payment_feat import (
    execute_insurance_premium_payment,
    settle_insurance_premium,
)
from app.feats.purchase_insurance_feat import execute_purchase_insurance
from app.models import BillCycle, EntitlementEvent, InsuranceClaim, ObligationAssessment
from app.scheduled_tasks import (
    SCHEDULED_JOB_SPECS,
    run_insurance_expiry_job,
    run_insurance_renewal_job,
)
from app.services import obligations_service
from app.services.context_resolver import CanonicalContext
from app.services.insurance_coverage_service import (
    evaluate_insurance_usability,
    is_insurance_usable,
    premium_lineage_ref,
)
from app.utils import canonical_temporal_resolver as resolver_module
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize
from tests.helpers.ledger import create_ledger_idempotent_transaction


_CLASS_TZ = pytz.timezone("America/Los_Angeles")


def local(month, day, hour=0, minute=0, year=2027):
    """A class-local (America/Los_Angeles) wall time, as UTC."""
    return _CLASS_TZ.localize(datetime(year, month, day, hour, minute)).astimezone(timezone.utc)


US = timedelta(microseconds=1)

# Weekly lineage purchased Sunday Jan 10 2027, 15:00 local. Anchor = Jan 10.
PURCHASE = local(1, 10, 15)
B1, B2, B3, B4 = local(1, 17), local(1, 24), local(1, 31), local(2, 7)
# Bill preview 3 days: period n+1 is assessed at B_n minus 3 class-local days.
PREVIEW_2, PREVIEW_3, PREVIEW_4 = local(1, 14), local(1, 21), local(1, 28)
PREMIUM = Decimal("10.00")


# --------------------------------------------------------------------------- #
# Harness                                                                      #
# --------------------------------------------------------------------------- #


@contextmanager
def _clock(at):
    real = resolver_module.datetime

    class _Frozen(real):
        @classmethod
        def now(cls, tz=None):
            return at if tz is not None else at.replace(tzinfo=None)

    resolver_module.datetime = _Frozen
    try:
        yield
    finally:
        resolver_module.datetime = real


class World:
    """One class, one student, one insurance policy, driven on a test clock."""

    def __init__(self, app, **policy):
        self.classroom = initialize("chemistry_p1", app)
        self.class_id = self.classroom.class_id
        self.student = self.classroom.students[0]
        self.seat_id = self.student.seat.id
        enable_class_feature(class_id=self.class_id, feature="insurance")
        submission = dict(
            insurance_type="TRANSACTION", premium=str(PREMIUM), charge_frequency="WEEKLY",
            reimbursement_percentage="100", payout_multiple="5",
            claims_per_week_equivalent="1", claim_window_days="7",
            bill_preview_days=3, nonpayment_mode="ACCUMULATE", title="Cover",
        )
        submission.update(policy)
        self.policy_uuid = configure_insurance_definition(
            class_id=self.class_id,
            submission=submission,
            canonical_context=self.teacher_ctx,
            correlation_id=f"corr_{uuid4().hex}",
            idempotency_key=f"FEAT-CLASS-003:configure:{uuid4().hex}",
        ).policy_uuid
        db.session.commit()
        self.entitlement_id = None

    @property
    def student_ctx(self):
        return CanonicalContext(
            user_id=self.student.user.id, class_id=self.class_id,
            seat_id=self.seat_id, actor_role="student",
        )

    @property
    def teacher_ctx(self):
        return CanonicalContext(
            user_id=self.classroom.teacher_user.id, class_id=self.class_id,
            seat_id=self.classroom.teacher_seat.id, actor_role="teacher",
        )

    @property
    def lineage(self):
        return premium_lineage_ref(self.entitlement_id)

    def fund(self, at, amount=PREMIUM):
        with _clock(at):
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"fund:{uuid4().hex}"):
                create_ledger_idempotent_transaction(
                    idempotency_key=f"fund:{uuid4().hex}", seat_id=self.seat_id,
                    class_id=self.class_id, amount=Decimal(amount),
                    account_type="checking", type="payroll", description="Test funding",
                )
            db.session.commit()

    def buy(self, at=PURCHASE):
        with _clock(at):
            result = execute_purchase_insurance(
                canonical_context=self.student_ctx, policy_uuid=self.policy_uuid,
                idempotency_key=f"buy:{uuid4().hex}",
            )
            db.session.commit()
        assert result.success, result.error_message
        self.entitlement_id = result.entitlement_id
        return result

    def renew(self, at):
        with _clock(at):
            result = execute_insurance_coverage_renewal(
                class_id=self.class_id, entitlement_id=self.entitlement_id,
                idempotency_key=f"FEAT-STOR-007:test:{uuid4().hex}",
            )
            db.session.commit()
        return result

    def pay(self, at, correlation_id=None):
        with _clock(at):
            result = execute_insurance_premium_payment(
                class_id=self.class_id, seat_id=self.seat_id,
                entitlement_id=self.entitlement_id, correlation_id=correlation_id,
                idempotency_key=f"pay:{uuid4().hex}",
            )
            db.session.commit()
        assert result.success, result.error_message
        return result

    def usable(self, at):
        return is_insurance_usable(self.class_id, self.entitlement_id, reference_time_utc=at)

    def cycles(self):
        return (
            BillCycle.query.filter_by(class_id=self.class_id, internal_ref=self.lineage)
            .order_by(BillCycle.cycle_number.asc()).all()
        )

    def premium_state(self, cycle_number):
        return obligations_service.get_obligation_state(
            premium_correlation_id(self.entitlement_id, cycle_number)
        )

    def expired_events(self):
        return EntitlementEvent.query.filter_by(
            class_id=self.class_id, entitlement_id=self.entitlement_id, event_type="EXPIRED",
        ).all()

    def loss(self, at, amount="-8.00"):
        with _clock(at):
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"loss:{uuid4().hex}"):
                txn, _ = create_ledger_idempotent_transaction(
                    idempotency_key=f"loss:{uuid4().hex}", seat_id=self.seat_id,
                    class_id=self.class_id, amount=Decimal(amount),
                    account_type="checking", type="purchase",
                    description="Insurance claim source loss",
                )
                txn_id = txn.id
            db.session.commit()
        return txn_id

    def file_claim(self, at, transaction_id, reference=None):
        with _clock(at):
            result = submit_insurance_claim(
                canonical_context=self.student_ctx, entitlement_id=self.entitlement_id,
                claim_subject={"transaction_id": transaction_id},
                correlation_id=f"claim:{uuid4().hex}",
                reference_time_utc=reference,
            )
            db.session.commit()
        return result


@pytest.fixture
def world(app):
    with app.app_context():
        yield lambda **policy: World(app, **policy)


# --------------------------------------------------------------------------- #
# Advance assessment and rollover                                              #
# --------------------------------------------------------------------------- #


def test_advance_payment_gives_uninterrupted_rollover(world):
    w = world()
    w.fund(PURCHASE - timedelta(hours=1), PREMIUM * 3)
    w.buy()

    # Before the assessment point nothing is due and nothing is written.
    early = w.renew(PREVIEW_2 - US)
    assert not early.wrote_anything
    assert [c.cycle_number for c in w.cycles()] == [1]

    result = w.renew(PREVIEW_2)
    assert result.cycles_scheduled == [2]
    assert result.premiums_autopaid == [premium_correlation_id(w.entitlement_id, 2)]
    cycle1, cycle2 = w.cycles()
    assert (cycle1.cycle_boundary_at, cycle1.next_assessment_at) == (PURCHASE, B1)
    assert (cycle2.cycle_boundary_at, cycle2.next_assessment_at) == (B1, B2)
    assert w.premium_state(2).is_satisfied
    # Due at its own boundary, not at assessment (DOM-OBL-001 §VIII).
    assert w.premium_state(2).due_at == B1

    # Continuous coverage across the boundary.
    for t in (B1 - US, B1, B1 + timedelta(days=3)):
        assert w.usable(t), t


def test_rerun_is_idempotent(world):
    w = world()
    w.fund(PURCHASE - timedelta(hours=1), PREMIUM * 3)
    w.buy()
    w.renew(PREVIEW_2)
    again = w.renew(PREVIEW_2 + timedelta(hours=1))
    assert not again.wrote_anything
    assert [c.cycle_number for c in w.cycles()] == [1, 2]
    premiums = ObligationAssessment.query.filter_by(
        internal_ref=w.lineage, event_type="ASSESSMENT").count()
    payments = ObligationAssessment.query.filter_by(
        internal_ref=w.lineage, event_type="PAYMENT").count()
    assert (premiums, payments) == (2, 2)


def test_unpaid_next_premium_gates_the_new_period(world):
    w = world()
    w.fund(PURCHASE - timedelta(hours=1))  # exactly the first premium
    w.buy()
    result = w.renew(PREVIEW_2)
    assert result.premiums_left_outstanding == [premium_correlation_id(w.entitlement_id, 2)]
    assert result.cycles_scheduled == [2]  # the failed attempt still commits

    assert w.usable(B1 - US)  # the paid period runs to its end
    gated = evaluate_insurance_usability(w.class_id, w.entitlement_id, reference_time_utc=B1)
    assert (gated.usable, gated.reason) == (False, "PREMIUM_UNPAID")


def test_failed_autopay_is_recoverable_by_manual_payment_before_the_boundary(world):
    w = world()
    w.fund(PURCHASE - timedelta(hours=1))
    w.buy()
    w.renew(PREVIEW_2)
    w.fund(local(1, 15))
    paid = w.pay(local(1, 15, 9))
    assert paid.correlation_id == premium_correlation_id(w.entitlement_id, 2)
    assert w.usable(B1)  # paid before the boundary: no gap


def test_late_payment_restores_prospectively_and_a_gated_claim_stays_invalid(world):
    w = world()
    w.fund(PURCHASE - timedelta(hours=1))
    w.buy()
    w.renew(PREVIEW_2)
    loss = w.loss(local(1, 18, 9))

    gated = w.file_claim(local(1, 18, 10), loss)
    assert (gated.success, gated.error_code) == (False, "COVERAGE_GATED")

    w.fund(local(1, 19, 11), PREMIUM * 2)  # the 8.00 loss also drew on checking
    paid_at = local(1, 19, 12)
    w.pay(paid_at)
    assert not w.usable(paid_at - US)
    assert w.usable(paid_at)

    # A later payment never validates the gated interval: filing "as of" the
    # gated time is still refused, and nothing was recorded for it.
    still_gated = w.file_claim(local(1, 19, 13), loss, reference=local(1, 18, 10))
    assert (still_gated.success, still_gated.error_code) == (False, "COVERAGE_GATED")
    assert InsuranceClaim.query.filter_by(entitlement_id=w.entitlement_id).count() == 0

    # From the payment forward the claim can be filed.
    ok = w.file_claim(local(1, 19, 14), loss)
    assert ok.success, ok.error_message


# --------------------------------------------------------------------------- #
# ACCUMULATE                                                                   #
# --------------------------------------------------------------------------- #


def test_accumulate_keeps_assessing_and_only_full_payment_restores(world):
    w = world()
    w.fund(PURCHASE - timedelta(hours=1))
    w.buy()
    w.renew(PREVIEW_2)
    w.renew(PREVIEW_3)
    w.renew(PREVIEW_4)
    # Premiums accumulate as outstanding obligations; nonpayment never terminates.
    assert [c.cycle_number for c in w.cycles()] == [1, 2, 3, 4]
    assert all(c.next_assessment_at is not None for c in w.cycles())
    assert w.premium_state(2).is_outstanding and w.premium_state(3).is_outstanding
    assert w.expired_events() == []
    assert not w.usable(local(1, 25))

    # Paying only the newest DUE premium restores nothing while an older one
    # is outstanding (DOM-STORE-001 §VIII.E.1).
    w.fund(local(1, 29), PREMIUM * 3)
    w.pay(local(1, 29, 9), correlation_id=premium_correlation_id(w.entitlement_id, 3))
    assert w.premium_state(3).is_satisfied
    assert not w.usable(local(1, 29, 10))

    # The default target is the oldest outstanding premium; paying it restores
    # usability for the then-current period — from that moment on only.
    restored_at = local(1, 29, 11)
    assert w.pay(restored_at).correlation_id == premium_correlation_id(w.entitlement_id, 2)
    assert not w.usable(restored_at - US)
    assert w.usable(restored_at)
    # Period 4 is advance-assessed and not yet due: not required.
    assert w.premium_state(4).is_outstanding


# --------------------------------------------------------------------------- #
# CANCEL_AFTER_X_DAYS                                                          #
# --------------------------------------------------------------------------- #


def test_cancel_after_x_days_longer_than_a_period(world):
    w = world(nonpayment_mode="CANCEL_AFTER_X_DAYS", cancel_after_days=10)
    w.fund(PURCHASE - timedelta(hours=1))
    w.buy()
    w.renew(PREVIEW_2)  # premium 2 fails; it lapses at B1
    deadline = local(1, 27)  # B1 + 10 class-local days

    # §V continues until the deadline: period 3 is assessed while premium 2 is
    # still delinquent, and that later assessment does not reset the deadline.
    third = w.renew(PREVIEW_3)
    assert third.cycles_scheduled == [3] and not third.terminated_for_nonpayment
    assert not w.renew(deadline - US).terminated_for_nonpayment
    assert w.expired_events() == []

    result = w.renew(PREVIEW_4)  # after the deadline, at period 4's assessment point
    assert result.terminated_for_nonpayment
    assert result.nonpayment_deadline == deadline
    assert result.cycles_scheduled == []  # no premium after termination

    [expired] = w.expired_events()
    assert expired.timestamp == deadline
    assert expired.payload["cause"] == "NONPAYMENT"
    terminal = w.cycles()[-1]
    assert (terminal.next_assessment_at, terminal.cycle_boundary_at) == (None, deadline)
    assert [c.cycle_number for c in w.cycles()] == [1, 2, 3, 4]  # 4 is the terminal row

    # Debt for periods that began before the deadline survives, still owed.
    assert w.premium_state(2).is_outstanding and w.premium_state(3).is_outstanding
    assert not w.usable(deadline) and w.usable(deadline - timedelta(days=4)) is False

    # Reruns never assess again and never expire twice.
    assert not w.renew(local(2, 20)).wrote_anything
    assert len(w.expired_events()) == 1
    assert ObligationAssessment.query.filter_by(
        internal_ref=w.lineage, event_type="ASSESSMENT").count() == 3

    # Late payment settles the debt and resurrects nothing.
    w.fund(local(2, 21), PREMIUM * 2)
    w.pay(local(2, 21, 9))
    w.pay(local(2, 21, 10))
    assert w.premium_state(2).is_satisfied and w.premium_state(3).is_satisfied
    assert not w.usable(local(2, 21, 11))
    assert not w.renew(local(2, 22)).wrote_anything


def test_late_job_withdraws_the_period_that_began_at_or_after_the_deadline(world):
    # X = 7 puts the deadline exactly on the next coverage boundary (B2).
    w = world(nonpayment_mode="CANCEL_AFTER_X_DAYS", cancel_after_days=7)
    w.fund(PURCHASE - timedelta(hours=1))
    w.buy()
    w.renew(PREVIEW_2)  # premium 2 fails; deadline = B1 + 7 days = B2
    w.renew(PREVIEW_3)  # before the deadline: period 3 [B2, B3) is assessed

    # The job next runs a week late, inside period 3.
    result = w.renew(local(2, 2))
    assert result.terminated_for_nonpayment and result.nonpayment_deadline == B2

    # Period 3 begins at the termination instant, so it never became effective:
    # its untouched premium is withdrawn, evaluated as of the deadline.
    assert w.premium_state(3).is_withdrawn
    assert w.premium_state(2).is_outstanding  # pre-termination debt survives
    assert not w.usable(B2)


def test_accumulate_never_terminates(world):
    w = world()
    w.fund(PURCHASE - timedelta(hours=1))
    w.buy()
    for t in (PREVIEW_2, PREVIEW_3, PREVIEW_4, local(2, 4), local(3, 1)):
        assert not w.renew(t).terminated_for_nonpayment
    assert w.expired_events() == []
    assert w.cycles()[-1].next_assessment_at is not None


# --------------------------------------------------------------------------- #
# Stopping renewal during the preview                                          #
# --------------------------------------------------------------------------- #


def _cancel(w, at):
    with _clock(at):
        result = execute_cancel_insurance(
            canonical_context=w.student_ctx, policy_uuid=w.policy_uuid,
            idempotency_key=f"cancel:{uuid4().hex}",
        )
        db.session.commit()
    assert result.success, result.error_message
    return result


def _expiry_job(at):
    with _clock(at):
        run_insurance_expiry_job()


def test_stop_renewal_with_unpaid_advance_premium_ends_at_current_period(world):
    w = world()
    w.fund(PURCHASE - timedelta(hours=1))
    w.buy()
    w.renew(PREVIEW_2)  # premium 2 assessed, unpaid

    cancelled = _cancel(w, local(1, 15))
    assert cancelled.coverage_boundary_at == B1
    assert w.premium_state(2).is_withdrawn  # never became owed

    _expiry_job(B1 + timedelta(hours=4))
    [expired] = w.expired_events()
    assert expired.timestamp == B1  # effective at the termination instant
    assert w.usable(B1 - US) and not w.usable(B1)
    assert not w.renew(local(1, 21)).wrote_anything


def test_stop_renewal_after_advance_payment_commits_the_period(world):
    w = world()
    w.fund(PURCHASE - timedelta(hours=1), PREMIUM * 2)
    w.buy()
    w.renew(PREVIEW_2)  # premium 2 autopaid → period 2 committed

    cancelled = _cancel(w, local(1, 15))
    assert cancelled.coverage_boundary_at == B2
    assert w.premium_state(2).is_satisfied
    assert w.usable(B1 + timedelta(days=2))
    _expiry_job(B1 + timedelta(hours=4))
    assert w.expired_events() == []  # not before the committed period ends
    _expiry_job(B2 + timedelta(hours=4))
    [expired] = w.expired_events()
    assert expired.timestamp == B2


def test_stop_renewal_after_partial_payment_commits_but_stays_gated(world):
    w = world()
    w.fund(PURCHASE - timedelta(hours=1), PREMIUM + Decimal("4.00"))
    w.buy()
    w.renew(PREVIEW_2)  # autopay fails: 4.00 < 10.00
    with _clock(local(1, 15)):
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"partial:{uuid4().hex}"):
            settle_insurance_premium(
                class_id=w.class_id, seat_id=w.seat_id,
                correlation_id=premium_correlation_id(w.entitlement_id, 2),
                amount=Decimal("4.00"), ledger_idempotency_key=f"partial:{uuid4().hex}",
                description="partial premium",
            )
        db.session.commit()

    cancelled = _cancel(w, local(1, 16))
    assert cancelled.coverage_boundary_at == B2  # any payment commits the period
    state = w.premium_state(2)
    assert state.is_outstanding and state.remaining_amount == Decimal("6.00")
    assert not w.usable(B1 + timedelta(days=1))  # gated until fully satisfied


# --------------------------------------------------------------------------- #
# Claims                                                                       #
# --------------------------------------------------------------------------- #


def test_claim_filed_during_valid_coverage_stays_adjudicable_after_lapse(world):
    w = world()
    w.fund(PURCHASE - timedelta(hours=1))
    w.buy()
    loss = w.loss(local(1, 12, 9))
    filed = w.file_claim(local(1, 12, 10), loss)
    assert filed.success, filed.error_message

    w.renew(PREVIEW_2)  # autopay fails; coverage lapses at B1
    assert not w.usable(local(1, 18))

    with _clock(local(1, 18, 12)):
        decided = resolve_insurance_claim(
            canonical_context=w.teacher_ctx, claim_id=filed.claim_id, approved=True,
            idempotency_key=f"approve:{uuid4().hex}",
        )
        db.session.commit()
    assert decided.success, decided.error_message
    assert decided.reimbursement_amount == Decimal("8.00")


def test_claim_allowance_is_per_coverage_period(world):
    w = world()  # claims_per_week_equivalent = 1
    w.fund(PURCHASE - timedelta(hours=1), PREMIUM * 4)  # premiums + the losses
    w.buy()
    first = w.file_claim(local(1, 12, 10), w.loss(local(1, 12, 9)))
    assert first.success, first.error_message
    second = w.file_claim(local(1, 13, 10), w.loss(local(1, 13, 9)))
    assert (second.success, second.error_code) == (False, "CLAIM_LIMIT_EXCEEDED")

    w.renew(PREVIEW_2)  # period 2 autopaid
    next_period = w.file_claim(local(1, 18, 10), w.loss(local(1, 18, 9)))
    assert next_period.success, next_period.error_message


def test_no_claim_after_stop_renewal_ends_coverage(world):
    w = world()
    w.fund(PURCHASE - timedelta(hours=1))
    w.buy()
    _cancel(w, local(1, 12))
    loss = w.loss(local(1, 17, 9))
    # The expiry job has not run yet; the ended period still cannot authorize.
    result = w.file_claim(local(1, 17, 10), loss)
    assert (result.success, result.error_code) == (False, "NO_COVERAGE_PERIOD")


# --------------------------------------------------------------------------- #
# Monthly anchored cadence                                                     #
# --------------------------------------------------------------------------- #


def test_monthly_purchase_on_the_31st_rolls_forward_from_the_anchor(world):
    w = world(charge_frequency="MONTHLY", bill_preview_days=3)
    purchase = local(1, 31, 10)
    w.fund(purchase - timedelta(hours=1), PREMIUM * 4)
    w.buy(purchase)
    w.renew(local(2, 26))  # Mar 1 − 3 days
    w.renew(local(3, 28))  # Mar 31 − 3 days
    w.renew(local(4, 28))  # May 1 − 3 days
    periods = [(c.cycle_boundary_at, c.next_assessment_at) for c in w.cycles()]
    # SPEC-TIME-001 §IX.12: Jan 31 → Mar 1 → Mar 31 → May 1 → May 31, every
    # boundary from the anchor (Feb 31 rolls forward; later months do not drift).
    assert periods == [
        (purchase, local(3, 1)),
        (local(3, 1), local(3, 31)),
        (local(3, 31), local(5, 1)),
        (local(5, 1), local(5, 31)),
    ]
    assert all(w.premium_state(n).assessed_amount == PREMIUM for n in (2, 3, 4))


# --------------------------------------------------------------------------- #
# Scheduled job                                                                #
# --------------------------------------------------------------------------- #


def test_renewal_job_is_registered_and_renews_due_entitlements(world):
    assert "insurance_renewal" in {spec.id for spec in SCHEDULED_JOB_SPECS}
    w = world()
    w.fund(PURCHASE - timedelta(hours=1), PREMIUM * 2)
    w.buy()
    with _clock(PREVIEW_2):
        run_insurance_renewal_job()
    assert [c.cycle_number for c in w.cycles()] == [1, 2]
    assert w.premium_state(2).is_satisfied
