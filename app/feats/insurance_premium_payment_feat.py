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

from app.feats.base import requires_feat_context
from app.feats.satisfy_obligation_feat import SatisfyObligationRequest, satisfy_obligation
from app.models import Seat, Transaction
from app.services import obligations_service
from app.services.identity_service import resolve_teacher_seat_for_class
from app.services.insurance_coverage_service import premium_lineage_ref
from app.services.ledger_balance_query_service import get_available_balance
from app.services.ledger_posting_service import create_pending_transaction_idempotent


def settle_insurance_premium(
    *,
    class_id: str,
    seat_id: int,
    correlation_id: str,
    amount: Decimal,
    ledger_idempotency_key: str,
    description: str,
    mechanism: str = "self",
    actor_seat_id: int | None = None,
) -> Transaction:
    """Debit ``amount`` toward one premium and record its ``PAYMENT``. Idempotent.

    The Ledger write is idempotent on ``ledger_idempotency_key`` and the PAYMENT
    on the Ledger row it references, so a replay writes nothing new.
    """
    if amount is None or Decimal(amount) <= Decimal("0.00"):
        raise ValueError("settle_insurance_premium requires a positive amount")
    authority_seat_id = resolve_teacher_seat_for_class(class_id).id
    transaction, _created = create_pending_transaction_idempotent(
        idempotency_key=ledger_idempotency_key,
        seat_id=seat_id,
        class_id=class_id,
        target_seat_id=authority_seat_id,
        actor_seat_id=actor_seat_id if actor_seat_id is not None else seat_id,
        mechanism=mechanism,
        amount=-Decimal(amount),
        account_type="checking",
        type="insurance_premium",
        description=description,
    )
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
    if get_available_balance(seat_id, class_id, "checking") < amount:
        return InsurancePremiumPaymentResult(
            correlation_id=state.correlation_id,
            error_code="INSUFFICIENT_FUNDS",
            error_message=f"Checking balance is below the {amount} premium due",
        )

    transaction = settle_insurance_premium(
        class_id=class_id,
        seat_id=seat_id,
        correlation_id=state.correlation_id,
        amount=amount,
        ledger_idempotency_key=f"insurance-premium-payment:{idempotency_key}",
        description=f"Insurance premium payment ({state.correlation_id})",
    )
    return InsurancePremiumPaymentResult(
        success=True,
        correlation_id=state.correlation_id,
        transaction_id=transaction.id,
        amount_paid=amount,
    )
