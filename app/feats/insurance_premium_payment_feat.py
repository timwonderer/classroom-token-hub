"""Insurance premium payment — the lawful Ledger + satisfaction path (FEAT-OBL-003).

One domain command, used by every premium payment: the purchase's first
premium (FEAT-OBL-004), automatic payment of an advance premium
(FEAT-STOR-007 §V.3), and a student's manual payment of an outstanding premium
(FEAT-STOR-007 §V: "the student may satisfy it manually at any later time,
before or after its due boundary, through the ordinary obligation payment
path").

``settle_insurance_premium`` posts the premium debit through the canonical
idempotent Ledger path and records the immutable ``PAYMENT`` referencing it
(DOM-OBL-001 §V.5). It is a plain command composed inside the caller's FEAT
context, never a nested FEAT.

``execute_insurance_premium_payment`` is the manual-payment executor. With no
selected assessment it pays the lineage's default target, the oldest
OUTSTANDING premium by due boundary (DOM-OBL-001 §VIII); callers do not order
premiums themselves.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db

from app.feats.base import requires_feat_context
from app.feats.satisfy_obligation_feat import SatisfyObligationRequest, satisfy_obligation
from app.models import BillCycle, Seat, Transaction
from app.services import insurance_definition_service, obligations_service
from app.services.identity_service import resolve_teacher_seat_for_class
from app.services.insurance_coverage_service import class_local_date, premium_lineage_ref
from app.services.ledger_balance_query_service import get_available_balance
from app.services.class_configuration_query_service import get_banking_directive
from app.services.ledger_resolution_service import build_intended_ledger_plan,resolve_intended_ledger_plan,apply_resolved_ledger_plan


def premium_description(class_id: str, correlation_id: str) -> str:
    """What a student sees for a premium: the policy and the period it pays for.

    e.g. "Insurance premium: Test Policy (Sep 25 – Oct 24)". The period is the
    premium's bill cycle, [start, next boundary), shown as its covered days.
    """
    assessment = obligations_service.get_assessment_for_correlation(correlation_id)
    title = "insurance policy"
    if assessment is not None and assessment.policy_uuid:
        definition = insurance_definition_service.get_insurance_definition(
            assessment.policy_uuid, class_id=class_id
        )
        if definition is not None and definition.title:
            title = definition.title
    cycle = db.session.get(BillCycle, assessment.bill_cycle_id) if assessment and assessment.bill_cycle_id else None
    if cycle is None or cycle.next_assessment_at is None:
        return f"Insurance premium: {title}"
    first = class_local_date(class_id, cycle.cycle_boundary_at)
    last = obligations_service.last_class_day_before(class_id, cycle.next_assessment_at)
    fmt = lambda d: d.strftime("%b %d").replace(" 0", " ")
    return f"Insurance premium: {title} ({fmt(first)} – {fmt(last)})"


def settle_insurance_premium(
    *,
    class_id: str,
    seat_id: int,
    correlation_id: str,
    amount: Decimal,
    ledger_idempotency_key: str,
    description: str | None = None,
    mechanism: str = "self",
    actor_seat_id: int | None = None,
    canonical_intent: tuple | None = None,
) -> Transaction:
    """Debit ``amount`` toward one premium and record its ``PAYMENT``. Idempotent.

    The Ledger write is idempotent on ``ledger_idempotency_key`` and the PAYMENT
    on the Ledger row it references, so a replay writes nothing new.
    """
    if amount is None or Decimal(amount) <= Decimal("0.00"):
        raise ValueError("settle_insurance_premium requires a positive amount")
    if description is None:
        description = premium_description(class_id, correlation_id)
    from app.services.ledger_recovery_service import lock_recovery_scope
    lock_recovery_scope(class_id,seat_id)
    authority_seat_id = resolve_teacher_seat_for_class(class_id).id
    intended=build_intended_ledger_plan(seat_id=seat_id,class_id=class_id,debit_amount=amount,
        transaction_type='insurance_premium',description=description,target_seat_id=authority_seat_id,
        actor_seat_id=actor_seat_id if actor_seat_id is not None else seat_id,mechanism=mechanism, canonical_intent=canonical_intent)
    resolved=resolve_intended_ledger_plan(plan=intended,banking_directive=get_banking_directive(class_id),fee_authority='NONE')
    transaction=apply_resolved_ledger_plan(resolved_plan=resolved,idempotency_key=ledger_idempotency_key)['principal']
    satisfy_obligation(
        SatisfyObligationRequest(
            correlation_id=correlation_id,
            class_id=class_id,
            seat_id=seat_id,
            method="PAYMENT",
            ledger_transaction_id=transaction.id,
        ),
        context=None,
    )
    return transaction


@dataclass
class InsurancePremiumPaymentResult:
    success: bool = False
    correlation_id: str | None = None
    transaction_id: int | None = None
    amount_paid: Decimal = Decimal("0.00")
    error_code: str | None = None
    error_message: str | None = None


@requires_feat_context("FEAT-OBL-003")
def execute_insurance_premium_payment(
    *,
    class_id: str,
    seat_id: int,
    entitlement_id: str,
    idempotency_key: str,
    correlation_id: str | None = None,
) -> InsurancePremiumPaymentResult:
    """A student pays one outstanding premium of an insurance entitlement in full.

    ``correlation_id`` selects a premium; omitted, the oldest outstanding premium
    of the entitlement's lineage is paid. A withdrawn or satisfied premium is not
    payable. Payment after termination settles that premium only and never
    resurrects the entitlement (DOM-STORE-001 §VIII.E.1).
    """
    if not idempotency_key:
        raise ValueError("execute_insurance_premium_payment requires an idempotency_key")
    lineage = premium_lineage_ref(entitlement_id)

    # The seat row serializes this seat's money (INV-LED-015).
    seat = Seat.query.filter_by(id=seat_id, class_id=class_id).with_for_update().first()
    if seat is None:
        return InsurancePremiumPaymentResult(
            error_code="NO_SEAT", error_message="Seat not found in class scope",
        )

    from app.services.ledger_recovery_service import lock_recovery_scope
    lock_recovery_scope(class_id,seat_id)

    from app.services.ledger_command_service import replay_reserved_charge
    canonical_intent = ("INSURANCE_PREMIUM", entitlement_id, correlation_id)
    prior = replay_reserved_charge(class_id=class_id, feat_code="FEAT-OBL-003",
        idempotency_key=f"insurance-premium-payment:{idempotency_key}", seat_id=seat_id,
        actor_seat_id=seat_id, principal_type="insurance_premium", canonical_intent=canonical_intent)
    if prior:
        principal = prior["principal"]
        payment = obligations_service.get_payment_event_by_ledger(principal.id)
        state = obligations_service.get_obligation_state(payment.correlation_id) if payment else None
        if state is None or state.class_id != class_id or state.seat_id != seat_id or state.internal_ref != lineage:
            raise ValueError("Accepted premium payment evidence is unavailable.")
        return InsurancePremiumPaymentResult(success=True, correlation_id=state.correlation_id,
            transaction_id=principal.id, amount_paid=abs(Decimal(principal.amount)))

    if correlation_id is None:
        state = obligations_service.get_default_payment_target(class_id, lineage)
    else:
        state = obligations_service.get_obligation_state(correlation_id)
        if state is not None and (state.internal_ref != lineage or state.class_id != class_id):
            state = None
    if state is None or state.seat_id != seat_id:
        return InsurancePremiumPaymentResult(
            correlation_id=correlation_id,
            error_code="NOTHING_TO_PAY",
            error_message="No outstanding premium on this coverage",
        )
    if not state.is_payable:
        return InsurancePremiumPaymentResult(
            correlation_id=state.correlation_id,
            error_code="NOT_PAYABLE",
            error_message=f"Premium is {state.status.value}",
        )

    amount = state.remaining_amount

    transaction = settle_insurance_premium(
        class_id=class_id,
        seat_id=seat_id,
        correlation_id=state.correlation_id,
        amount=amount,
        ledger_idempotency_key=f"insurance-premium-payment:{idempotency_key}",
        canonical_intent=canonical_intent,
    )
    return InsurancePremiumPaymentResult(
        success=True,
        correlation_id=state.correlation_id,
        transaction_id=transaction.id,
        amount_paid=amount,
    )
