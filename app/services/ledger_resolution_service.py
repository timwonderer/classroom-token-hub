"""Ledger monetary plans; callers supply resolved identity and Class directives.

FEAT-LED-000 XI.5; DOM-LED-001 VII. No domain eligibility/configuration lookup
occurs here, and no FEAT context is opened by these domain interfaces.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from app.extensions import db
from app.models import Transaction, _quantize_currency
from app.services.ledger_balance_query_service import get_available_balances
from app.services.ledger_command_service import create_reserved_effects


@dataclass(frozen=True)
class IntendedLedgerPlan:
    seat_id: int
    class_id: str
    debit_amount: Decimal
    description: str
    transaction_type: str
    actor_seat_id: int
    target_seat_id: int
    mechanism: str
    fee_actor_seat_id: int | None = None
    source_account: str = "checking"
    target_account: str | None = None
    compensation_origin_locator: str | None = None
    correction_intent_locator: str | None = None
    original_transaction_id: int | None = None
    correlation_id: str | None = None
    canonical_intent: tuple | None = None


@dataclass(frozen=True)
class ResolvedLedgerPlan:
    outcome: str
    intended_plan: IntendedLedgerPlan
    shortfall: Decimal
    recovery_transfer_amount: Decimal
    overdraft_fee_amount: Decimal
    checking_before: Decimal
    savings_before: Decimal
    checking_after: Decimal
    savings_after: Decimal
    directive_identity: tuple


def build_intended_ledger_plan(
    *,
    seat_id,
    class_id,
    debit_amount,
    description,
    transaction_type,
    actor_seat_id,
    target_seat_id,
    mechanism,
    fee_actor_seat_id=None,
    source_account="checking",
    target_account=None,
    compensation_origin_locator=None,
    correction_intent_locator=None,
    original_transaction_id=None,
    correlation_id=None,
    canonical_intent=None,
):
    amount = _quantize_currency(debit_amount)
    if amount < 0 or source_account not in {"checking", "savings"}:
        raise ValueError("Charge plans require a nonnegative canonical-account debit.")
    return IntendedLedgerPlan(
        seat_id,
        class_id,
        amount,
        description,
        transaction_type,
        actor_seat_id,
        target_seat_id,
        mechanism,
        fee_actor_seat_id,
        source_account,
        target_account,
        compensation_origin_locator,
        correction_intent_locator,
        original_transaction_id,
        correlation_id,
        canonical_intent,
    )


def directive_identity(directive, *, include_fees=False):
    base = (directive.class_id, directive.version_locator, directive.protection_enabled)
    return (
        base
        + (
            str(directive.flat_fee),
            directive.progressive_fee,
            str(directive.cwi),
            (
                directive.fee_period_start.isoformat()
                if directive.fee_period_start
                else None
            ),
        )
        if include_fees
        else base
    )


def _fee_amount(plan, directive):
    if directive.flat_fee is not None:
        flat = Decimal(directive.flat_fee)
        if not flat.is_finite() or flat < 0:
            raise ValueError("Invalid banking fee directive.")
        return _quantize_currency(flat)
    if directive.progressive_fee is None:
        raise ValueError("Unavailable banking fee directive.")
    if not directive.progressive_fee:
        return Decimal("0.00")
    if directive.cwi is None or directive.fee_period_start is None:
        raise ValueError("Unavailable banking fee directive.")
    if not directive.cwi.is_finite() or directive.cwi < 0:
        raise ValueError("Invalid banking fee directive.")
    count = Transaction.query.filter(
        Transaction.class_id == plan.class_id,
        Transaction.seat_id == plan.seat_id,
        Transaction.type == "overdraft_fee",
        Transaction.timestamp >= directive.fee_period_start,
    ).count()
    tier = "tier_1" if count == 0 else "tier_2" if count == 1 else "tier_3"
    raw = dict(directive.progressive_fee).get(tier)
    try:
        rate = Decimal(str(raw).strip().rstrip("%")) / 100
    except (ValueError, InvalidOperation):
        raise ValueError("Unavailable banking fee directive.")
    if not rate.is_finite() or rate < 0:
        raise ValueError("Invalid banking fee directive.")
    return _quantize_currency(directive.cwi * rate)


def resolve_intended_ledger_plan(
    *, plan, banking_directive, fee_authority="NONE", force_overdraft_fee=False
):
    if banking_directive.class_id != plan.class_id or fee_authority not in {
        "NONE",
        "FAILED_AGREEMENT",
        "EXPLICIT_FEE",
    }:
        raise ValueError("Invalid funding directive scope or fee authority.")
    checking, savings = get_available_balances(plan.seat_id, plan.class_id)
    principal = plan.debit_amount
    if plan.source_account == "savings":
        if fee_authority != "NONE":
            raise ValueError("Savings recovery cannot create a checking fee.")
        return ResolvedLedgerPlan(
            "ACCEPT",
            plan,
            Decimal("0.00"),
            Decimal("0.00"),
            Decimal("0.00"),
            checking,
            savings,
            checking,
            savings - principal,
            (),
        )
    shortfall = max(principal - checking, Decimal("0.00"))
    can_protect = banking_directive.protection_enabled and savings >= shortfall
    fee = Decimal("0.00")
    if fee_authority == "EXPLICIT_FEE" and (force_overdraft_fee or checking < 0):
        fee = _fee_amount(plan, banking_directive)
    elif fee_authority == "FAILED_AGREEMENT" and shortfall > 0 and (not can_protect):
        fee = _fee_amount(plan, banking_directive)
    total = principal + fee
    shortfall = max(total - checking, Decimal("0.00")) if total else Decimal("0.00")
    transfer = (
        shortfall
        if shortfall > 0
        and banking_directive.protection_enabled
        and (savings >= shortfall)
        else Decimal("0.00")
    )
    return ResolvedLedgerPlan(
        "TRANSFORM" if transfer or fee else "ACCEPT",
        plan,
        shortfall,
        transfer,
        fee,
        checking,
        savings,
        checking + transfer - total,
        savings - transfer,
        directive_identity(banking_directive, include_fees=fee_authority != "NONE"),
    )


def apply_resolved_ledger_plan(*, resolved_plan, idempotency_key):
    """One reservation owns principal, funding legs and any separately authorized fee."""
    from app.feats.base import get_active_feat_name

    p = resolved_plan.intended_plan
    effects = []
    common = dict(
        seat_id=p.seat_id,
        class_id=p.class_id,
        target_seat_id=p.target_seat_id,
        actor_seat_id=p.actor_seat_id,
        mechanism=p.mechanism,
        correlation_id=p.correlation_id,
    )
    transfer = resolved_plan.recovery_transfer_amount
    if transfer:
        import hashlib

        funding_correlation = (
            "corr_funding_"
            + hashlib.sha256(
                f"{p.class_id}:{get_active_feat_name()}:{idempotency_key}:funding".encode()
            ).hexdigest()[:32]
        )
        for account, amount, text in [
            ("savings", -transfer, "to checking"),
            ("checking", transfer, "from savings"),
        ]:
            effects.append(
                dict(
                    common,
                    target_seat_id=p.seat_id,
                    correlation_id=funding_correlation,
                    account_type=account,
                    amount=amount,
                    type="Withdrawal" if amount < 0 else "Deposit",
                    description=f"Overdraft protection transfer {text}",
                )
            )
    principal_index = None
    if p.debit_amount:
        principal_index = len(effects)
        effects.append(
            dict(
                common,
                account_type=p.source_account,
                amount=-p.debit_amount,
                type=p.transaction_type,
                description=p.description,
                original_transaction_id=p.original_transaction_id,
                compensation_origin_locator=p.compensation_origin_locator,
                correction_intent_locator=p.correction_intent_locator,
                compensation_amount_cents=(
                    int(p.debit_amount * 100) if p.compensation_origin_locator else 0
                ),
            )
        )
    fee_index = None
    if resolved_plan.overdraft_fee_amount:
        if p.fee_actor_seat_id is None:
            raise ValueError("A fee requires its resolved authority actor.")
        fee_index = len(effects)
        effects.append(
            dict(
                common,
                actor_seat_id=p.fee_actor_seat_id,
                mechanism="system",
                target_seat_id=p.seat_id,
                account_type="checking",
                amount=-resolved_plan.overdraft_fee_amount,
                type="overdraft_fee",
                description="Non-sufficient funds fee",
            )
        )
    if not effects:
        return {
            "accepted": True,
            "reason": resolved_plan.outcome,
            "effects": (),
            "principal": None,
            "ledger_transaction_id": None,
        }
    from app.models import LedgerCommandReservation
    from app.services.ledger_recovery_service import lock_recovery_scope

    reservation = LedgerCommandReservation.query.filter_by(
        class_id=p.class_id,
        feat_code=get_active_feat_name(),
        idempotency_key=idempotency_key,
    ).first()
    if reservation is None:
        lock_recovery_scope(p.class_id, p.seat_id)
        checking, savings = get_available_balances(p.seat_id, p.class_id)
        if (
            checking != resolved_plan.checking_before
            or savings != resolved_plan.savings_before
        ):
            raise ValueError("PREVIEW_CHANGED")
    rows, created = create_reserved_effects(
        class_id=p.class_id,
        feat_code=get_active_feat_name(),
        idempotency_key=idempotency_key,
        effects=effects,
        canonical_intent=p.canonical_intent,
    )
    return {
        "accepted": True,
        "reason": resolved_plan.outcome,
        "effects": tuple(rows),
        "created": created,
        "principal": rows[principal_index] if principal_index is not None else None,
        "ledger_transaction_id": rows[fee_index].id if fee_index is not None else None,
    }
