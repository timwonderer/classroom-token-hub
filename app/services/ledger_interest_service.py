"""Ledger-owned savings-interest command."""

from decimal import Decimal
from types import SimpleNamespace

from app.services.class_configuration_query_service import get_current_economic_engine
from app.services.economic_engine import savings_interest_for_payout_period
from app.services.ledger_balance_query_service import get_posted_balance
from app.services.ledger_posting_service import create_pending_transaction_idempotent
from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION,
    canonical_temporal_resolver,
)


def resolve_savings_policy(class_id):
    """The savings terms the Economic Engine actually configured for a class.

    Projections must read this rather than re-deriving it: SPEC-ECON-001 §10
    requires a forecast to use the same rules as execution, and §11 prohibits a
    hidden default APY. ``annual_rate`` is therefore ``None`` — not a stand-in
    figure — when the engine has set no rate, so a caller cannot accidentally
    advertise or pay interest a teacher never configured.
    """
    engine = get_current_economic_engine(class_id)
    return SimpleNamespace(
        engine=engine,
        annual_rate=(
            Decimal(str(engine.interest_rate))
            if engine and engine.interest_rate is not None
            else None
        ),
        calculation_type=(
            engine.interest_calculation_type if engine and engine.interest_calculation_type else "simple"
        ),
        compound_frequency=(
            engine.compound_frequency if engine and engine.compound_frequency else "never"
        ),
        payout_frequency=(
            engine.interest_payout_frequency if engine and engine.interest_payout_frequency else "monthly"
        ),
    )


def apply_monthly_savings_interest(seat, *, annual_rate=None):
    """Post one class-scoped monthly savings-interest effect when eligible."""
    if not seat:
        return None

    policy = resolve_savings_policy(seat.class_id)
    if annual_rate is None:
        annual_rate = policy.annual_rate
    if annual_rate is None or annual_rate <= Decimal("0"):
        return None

    calculation_type = policy.calculation_type
    compound_frequency = policy.compound_frequency
    payout_frequency = policy.payout_frequency

    ctx = SimpleNamespace(class_id=seat.class_id)
    now_eval = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="current_time",
    )
    month_bounds = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="evaluation_period_boundaries",
        period="month",
        reference_time_utc=now_eval.canonical_now_utc,
    )
    start_utc = month_bounds.result["boundary_start_utc"]

    interest = savings_interest_for_payout_period(
        posted_balance=get_posted_balance(seat.id, seat.class_id, "savings"),
        annual_rate=annual_rate,
        calculation_type=calculation_type,
        compound_frequency=compound_frequency,
        payout_frequency=payout_frequency,
    )
    if interest <= Decimal("0.00"):
        return None
    period_key = start_utc.strftime("%Y-%m")
    transaction, _created = create_pending_transaction_idempotent(
        idempotency_key=f"savings-interest:{seat.class_id}:{seat.id}:{period_key}",
        seat_id=seat.id,
        class_id=seat.class_id,
        target_seat_id=seat.id,
        actor_seat_id=seat.id,
        mechanism="self",
        user_id=seat.user_id,
        amount=interest,
        account_type="savings",
        type="Interest",
        description="Monthly Savings Interest",
    )
    return transaction


__all__ = ["apply_monthly_savings_interest"]
