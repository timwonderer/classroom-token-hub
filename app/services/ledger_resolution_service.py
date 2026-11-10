"""Ledger monetary plans; callers supply resolved identity and Class directives.

FEAT-LED-000 XI.5; DOM-LED-001 VII. No domain eligibility/configuration lookup
occurs here, and no FEAT context is opened by these domain interfaces.

No overdraft/NSF fee is ever resolved here (owner ruling 2026-10-07;
SPEC-ECON-003 §4.5.1.1): a shortfall this module cannot fund through savings
simply posts a negative checking balance (or, for an obligation payment or
purchase, is refused by the calling FEAT before anything posts).
"""

from dataclasses import dataclass
from decimal import Decimal
from app.models import _quantize_currency
from app.services.ledger_balance_query_service import get_available_balances
from app.services.ledger_command_service import create_reserved_effects
from app.services.ledger_transfer_service import build_transfer_effect_pair


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
    source_account: str = "checking"
    target_account: str | None = None
    compensation_origin_locator: str | None = None
    correction_intent_locator: str | None = None
    original_transaction_id: int | None = None
    correlation_id: str | None = None
    canonical_intent: tuple | None = None
    compensation_subtype: str | None = None


@dataclass(frozen=True)
class ResolvedLedgerPlan:
    outcome: str
    intended_plan: IntendedLedgerPlan
    shortfall: Decimal
    recovery_transfer_amount: Decimal
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
    source_account="checking",
    target_account=None,
    compensation_origin_locator=None,
    correction_intent_locator=None,
    original_transaction_id=None,
    correlation_id=None,
    canonical_intent=None,
    compensation_subtype=None,
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
        source_account,
        target_account,
        compensation_origin_locator,
        correction_intent_locator,
        original_transaction_id,
        correlation_id,
        canonical_intent,
        compensation_subtype,
    )


def directive_identity(directive):
    return (directive.class_id, directive.version_locator, directive.protection_enabled)


def resolve_intended_ledger_plan(*, plan, banking_directive):
    if banking_directive.class_id != plan.class_id:
        raise ValueError("Invalid funding directive scope.")
    checking, savings = get_available_balances(plan.seat_id, plan.class_id)
    principal = plan.debit_amount
    if plan.source_account == "savings":
        return ResolvedLedgerPlan(
            "ACCEPT",
            plan,
            Decimal("0.00"),
            Decimal("0.00"),
            checking,
            savings,
            checking,
            savings - principal,
            (),
        )
    shortfall = max(principal - checking, Decimal("0.00"))
    transfer = (
        shortfall
        if shortfall > 0
        and banking_directive.protection_enabled
        and (savings >= shortfall)
        else Decimal("0.00")
    )
    return ResolvedLedgerPlan(
        "TRANSFORM" if transfer else "ACCEPT",
        plan,
        shortfall,
        transfer,
        checking,
        savings,
        checking + transfer - principal,
        savings - transfer,
        directive_identity(banking_directive),
    )


def apply_resolved_ledger_plan(*, resolved_plan, idempotency_key):
    """One reservation owns the principal debit and its overdraft-protection funding leg."""
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
        effects.extend(
            build_transfer_effect_pair(
                seat_id=p.seat_id,
                class_id=p.class_id,
                target_seat_id=p.seat_id,
                actor_seat_id=p.actor_seat_id,
                mechanism=p.mechanism,
                correlation_id=funding_correlation,
                amount=transfer,
                from_account="savings",
                to_account="checking",
                withdraw_description="Overdraft protection transfer to checking",
                deposit_description="Overdraft protection transfer from savings",
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
                compensation_subtype=p.compensation_subtype,
                compensation_origin_locator=p.compensation_origin_locator,
                correction_intent_locator=p.correction_intent_locator,
                compensation_amount_cents=(
                    int(p.debit_amount * 100) if p.compensation_origin_locator else 0
                ),
            )
        )
    if not effects:
        return {
            "accepted": True,
            "reason": resolved_plan.outcome,
            "effects": (),
            "principal": None,
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
    }
