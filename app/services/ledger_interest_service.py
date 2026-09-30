"""Ledger-owned savings-interest command."""

import re
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import NamedTuple

from app.extensions import db
from app.models import Transaction, TransactionStatus
from app.services.class_configuration_query_service import get_current_economic_engine
from app.services.economic_engine import savings_interest_for_payout_period
from app.services.ledger_posting_service import create_pending_transaction_idempotent
from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION,
    canonical_temporal_resolver,
    ensure_utc,
)


# Payout cadence -> the SPEC-TIME-001 §11 calendar period that bounds one payout
# window. Weeks are Monday-start and months are calendar months, both in the
# class timezone; the resolver owns that arithmetic (SPEC-ECON-001 §2.3, §11).
_WINDOW_PERIOD = {"weekly": "week", "monthly": "month"}

# Window-keyed payout starts with the first class-local week that held real
# ledger money (the week of Monday 2026-09-28). No window ending on or before
# this date is ever paid by the job; paying earlier windows would be back-pay,
# which is an owner decision rather than something the scheduler infers.
WINDOW_KEYED_PAYOUT_START = date(2026, 9, 28)

# Before payouts were keyed by window they were keyed by calendar month
# (``...:{YYYY-MM}``) and paid one payout period whenever the first hourly tick
# of the month saw a positive balance. Such a row is treated as having paid the
# configured-cadence window it was posted in, so no window is paid twice.
_LEGACY_MONTH_SUFFIX = re.compile(r"^\d{4}-\d{2}$")
_WINDOW_SUFFIX = re.compile(r"^(weekly):(\d{4}-\d{2}-\d{2})$|^(monthly):(\d{4})-(\d{2})$")


class PayoutWindow(NamedTuple):
    """One class-local payout window, half-open ``[start_utc, end_utc)``."""

    cadence: str
    key: str
    start_utc: object
    end_utc: object


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


def payout_window_containing(class_id, payout_frequency, instant_utc):
    """The class-local payout window of ``payout_frequency`` containing an instant."""
    cadence = (payout_frequency or "monthly").strip().lower()
    if cadence not in _WINDOW_PERIOD:
        raise ValueError(f"Unsupported payout_frequency: {payout_frequency!r}")
    bounds = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=SimpleNamespace(class_id=class_id),
        primitive="evaluation_period_boundaries",
        period=_WINDOW_PERIOD[cadence],
        reference_time_utc=ensure_utc(instant_utc),
    ).result
    local_start = bounds["boundary_start"].date()
    key = (
        f"weekly:{local_start.isoformat()}"
        if cadence == "weekly"
        else f"monthly:{local_start:%Y-%m}"
    )
    return PayoutWindow(cadence, key, bounds["boundary_start_utc"], bounds["boundary_end_utc"])


def _class_local_midnight_utc(class_id, local_date):
    return canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=SimpleNamespace(class_id=class_id),
        primitive="anchored_recurrence_boundary",
        anchor_date=local_date,
        cadence="week",
        index=0,
    ).boundary_start_utc


def savings_interest_idempotency_key(class_id, seat_id, window):
    """One payout per seat per window (SPEC-ECON-001 §8.2)."""
    return f"savings-interest:{class_id}:{seat_id}:{window.key}"


def _paid_window(class_id, payout_frequency, transaction, prefix):
    """The window an existing interest row paid, or ``None`` if unrecognised."""
    suffix = (transaction.idempotency_key or "")[len(prefix):]
    match = _WINDOW_SUFFIX.match(suffix)
    if match and match.group(1):
        local_start = date.fromisoformat(match.group(2))
        return payout_window_containing(
            class_id, "weekly", _class_local_midnight_utc(class_id, local_start)
        )
    if match:
        local_start = date(int(match.group(4)), int(match.group(5)), 1)
        return payout_window_containing(
            class_id, "monthly", _class_local_midnight_utc(class_id, local_start)
        )
    if _LEGACY_MONTH_SUFFIX.match(suffix):
        return payout_window_containing(class_id, payout_frequency, transaction.timestamp)
    return None


def _posted_savings_history(seat_id, class_id):
    """``(posted_at, amount_cents)`` for every posted savings effect, oldest first.

    Posted status and ``posted_at`` are fixed at settlement, so a window's base
    reconstructed from them is the same on every replay (SPEC-ECON-001 §9.2, §12).
    Voided effects never reach POSTED and so never contribute (§9.3).
    """
    return (
        db.session.query(Transaction.posted_at, Transaction.amount_cents)
        .filter(
            Transaction.seat_id == seat_id,
            Transaction.class_id == class_id,
            Transaction.account_type == "savings",
            Transaction.status == TransactionStatus.POSTED,
            Transaction.posted_at.isnot(None),
        )
        .order_by(Transaction.posted_at.asc(), Transaction.id.asc())
        .all()
    )


def _posted_balance_before(history, instant_utc):
    """Posted savings balance at a window boundary: effects posted before it."""
    cents = sum(amount for posted_at, amount in history if ensure_utc(posted_at) < instant_utc)
    return (Decimal(cents) / 100).quantize(Decimal("0.01"))


def apply_savings_interest(seat, *, annual_rate=None, reference_time_utc=None):
    """Pay every closed, unpaid payout window for one seat, oldest first.

    SPEC-ECON-001 §14.1: resolve the class-local boundary, determine which payout
    windows have closed since the last settled one, and pay each exactly once.
    The window is the teacher-configured ``interest_payout_frequency`` — a
    Monday-start class-local week or a class-local calendar month — and its base
    is the posted savings balance at the instant the window closed. Returns the
    transactions created by this call.
    """
    if not seat:
        return []

    policy = resolve_savings_policy(seat.class_id)
    if annual_rate is None:
        annual_rate = policy.annual_rate
    if annual_rate is None or annual_rate <= Decimal("0"):
        return []

    class_id = seat.class_id
    cadence = (policy.payout_frequency or "monthly").strip().lower()
    now_utc = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=SimpleNamespace(class_id=class_id),
        primitive="current_time",
        reference_time_utc=reference_time_utc,
    ).canonical_now_utc

    history = _posted_savings_history(seat.id, class_id)
    if not history:
        return []

    # A window is payable only after the latest one already paid, under any
    # cadence or key format. A cadence change therefore never pays days twice.
    prefix = f"savings-interest:{class_id}:{seat.id}:"
    paid_rows = (
        Transaction.query
        .filter(
            Transaction.seat_id == seat.id,
            Transaction.class_id == class_id,
            Transaction.type == "Interest",
            Transaction.status != TransactionStatus.VOID,
            Transaction.idempotency_key.like(f"{prefix}%"),
        )
        .all()
    )
    paid_keys = {row.idempotency_key for row in paid_rows}
    paid_through = None
    for row in paid_rows:
        window = _paid_window(class_id, cadence, row, prefix)
        if window is not None and (paid_through is None or window.end_utc > paid_through):
            paid_through = window.end_utc

    # Nothing before the window-keyed start, before the seat's first posted
    # savings effect, or before the seat was claimed can earn a payout.
    floors = [
        _class_local_midnight_utc(class_id, WINDOW_KEYED_PAYOUT_START),
        ensure_utc(history[0][0]),
    ]
    if seat.claimed_at is not None:
        floors.append(ensure_utc(seat.claimed_at))
    if paid_through is not None:
        floors.append(paid_through)
    floor_utc = max(floors)

    created = []
    window = payout_window_containing(class_id, cadence, floor_utc)
    while window.end_utc <= now_utc:
        key = savings_interest_idempotency_key(class_id, seat.id, window)
        if key not in paid_keys and (paid_through is None or window.start_utc >= paid_through):
            interest = savings_interest_for_payout_period(
                posted_balance=_posted_balance_before(history, window.end_utc),
                annual_rate=annual_rate,
                calculation_type=policy.calculation_type,
                compound_frequency=policy.compound_frequency,
                payout_frequency=cadence,
            )
            if interest > Decimal("0.00"):
                transaction, was_created = create_pending_transaction_idempotent(
                    idempotency_key=key,
                    seat_id=seat.id,
                    class_id=class_id,
                    target_seat_id=seat.id,
                    actor_seat_id=seat.id,
                    mechanism="self",
                    amount=interest,
                    account_type="savings",
                    type="Interest",
                    description=f"{cadence.capitalize()} Savings Interest",
                )
                if was_created:
                    created.append(transaction)
        window = payout_window_containing(class_id, cadence, window.end_utc)
    return created


__all__ = [
    "WINDOW_KEYED_PAYOUT_START",
    "apply_savings_interest",
    "payout_window_containing",
    "resolve_savings_policy",
    "savings_interest_idempotency_key",
]
