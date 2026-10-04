"""Ledger-owned savings-interest command."""

import re
from bisect import insort
from datetime import date
from decimal import Decimal
from functools import lru_cache
from types import SimpleNamespace
from typing import NamedTuple

from app.extensions import db
from app.models import Seat, Transaction, TransactionStatus
from app.services.class_configuration_query_service import (
    economic_engine_timeline,
    get_current_economic_engine,
)
from app.services.economic_engine import (
    ProjectedSavingsDay,
    SavingsAccrualDay,
    accrue_daily_interest,
    credit_savings_interest,
    project_savings_balances,
)
from app.services.ledger_balance_query_service import (
    classify_posting_state,
    get_posted_balance,
    posting_scope_of,
    resolve_reconciliation_cursors,
)
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

# Compound frequency -> the calendar period whose start is a compounding boundary
# inside a payout window (SPEC-ECON-001 §6.2). Daily compounding needs no marker.
_COMPOUNDING_PERIOD = {"weekly": "week", "monthly": "month"}

# Window-keyed payout starts with the first class-local week that held real
# ledger money (the week of Monday 2026-09-28). No window ending on or before
# this date is ever paid by the job; paying earlier windows would be back-pay,
# which is an owner decision rather than something the scheduler infers.
WINDOW_KEYED_PAYOUT_START = date(2026, 9, 28)

# Before payouts were keyed by window they were keyed by calendar month
# (``...:{YYYY-MM}``) and paid one payout period whenever the first hourly tick
# of the month saw a positive balance. Such a row is treated as having paid the
# configured-cadence window it was posted in, so no window is paid twice. In
# production that is the week of 2026-09-28 (operator ruling 2026-09-30).
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


def _resolve(class_id, primitive, **inputs):
    return canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=SimpleNamespace(class_id=class_id),
        primitive=primitive,
        **inputs,
    )


def payout_window_containing(class_id, payout_frequency, instant_utc):
    """The class-local payout window of ``payout_frequency`` containing an instant."""
    cadence = (payout_frequency or "monthly").strip().lower()
    if cadence not in _WINDOW_PERIOD:
        raise ValueError(f"Unsupported payout_frequency: {payout_frequency!r}")
    bounds = _resolve(
        class_id,
        "evaluation_period_boundaries",
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
    return _resolve(
        class_id,
        "anchored_recurrence_boundary",
        anchor_date=local_date,
        cadence="week",
        index=0,
    ).boundary_start_utc


@lru_cache(maxsize=4096)
def _window_day_plan(class_id, compounding_period, start_utc, end_utc):
    """``(day_end_utc, capitalizes)`` for each class-local day of a window.

    Class timezones are immutable once set, so a window's days never change and
    are cached. Every boundary comes from the canonical resolver: a day is
    ``[00:00, 24:00)`` in class time (23 or 25 hours across DST), and a
    compounding boundary is a class-local week or month start.
    """
    plan = []
    day_start = start_utc
    while day_start < end_utc:
        day_end = _resolve(
            class_id, "evaluation_day_boundaries", reference_time_utc=day_start
        ).boundary_end_utc
        capitalizes = False
        if compounding_period is not None:
            capitalizes = _resolve(
                class_id,
                "evaluation_period_boundaries",
                period=compounding_period,
                reference_time_utc=day_start,
            ).boundary_start_utc == day_start
        plan.append((day_end, capitalizes))
        day_start = day_end
    return tuple(plan)


def _compounding_period(policy):
    if (policy.calculation_type or "simple").strip().lower() == "simple":
        return None
    return _COMPOUNDING_PERIOD.get((policy.compound_frequency or "never").strip().lower())


def _rate_timeline(class_id, annual_rate_override=None):
    """The annual rate in force at any instant (SPEC-ECON-001 §9.2, §12).

    Each accrual day takes the rate of the Economic Engine version in force at
    its end, as the one resolver answers it (``economic_engine_timeline``, the
    in-memory form of ``economic_engine_effective_at``, DOM-CLASS-003 §VII). A
    version saved mid-window and dated for later earns nothing before its date.
    An explicit override (the deterministic-replay path) applies to every day.
    """
    if annual_rate_override is not None:
        return (lambda _instant: annual_rate_override), annual_rate_override > 0
    timeline = economic_engine_timeline(class_id)

    def _rate(engine):
        if engine is None or engine.interest_rate is None:
            return None
        return Decimal(str(engine.interest_rate))

    def rate_at(instant_utc):
        return _rate(timeline.at(instant_utc))

    return rate_at, any(
        rate is not None and rate > 0 for rate in map(_rate, timeline.versions)
    )


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


class _SavingsLedger(NamedTuple):
    """A seat's savings ledger as the daily balance method reads it."""

    history: list        # ``(effective_utc, amount_cents)``, ascending
    paid_keys: set       # interest keys already credited
    paid_through: object  # end of the latest window already credited, or None


def _savings_ledger(seat_id, class_id, cadence):
    """Reconstruct a seat's savings balances and credited windows from the ledger.

    An ordinary savings effect participates from its posting time: only posted
    balances earn (SPEC-ECON-001 §9.2), and voided effects never do (§9.3). A
    savings-interest credit participates from the close of the window it pays,
    whether or not it has settled yet. Compounding across windows therefore
    does not depend on when the job ran or when settlement posted a credit, and
    a replay reconstructs the same balances (§9.2, §12, §14.1).

    A window is credited once. ``paid_through`` is the end of the latest window
    already credited, under any cadence or key format; no day ending at or
    before it accrues again, so a cadence change never pays a day twice (§8.2).
    """
    prefix = f"savings-interest:{class_id}:{seat_id}:"
    rows = (
        Transaction.query
        .filter(
            Transaction.seat_id == seat_id,
            Transaction.class_id == class_id,
            Transaction.account_type == "savings",
        )
        .all()
    )
    # Every row shares one account scope, so its cursor is read once, not per row.
    cursors = resolve_reconciliation_cursors(posting_scope_of(row) for row in rows)
    history = []
    paid_keys = set()
    paid_through = None
    for row in rows:
        window = None
        if row.type == "Interest" and (row.idempotency_key or "").startswith(prefix):
            window = _paid_window(class_id, cadence, row, prefix)
        if window is not None:
            paid_keys.add(row.idempotency_key)
            if paid_through is None or window.end_utc > paid_through:
                paid_through = window.end_utc
            history.append((window.end_utc, row.amount_cents))
        elif row.posted_at is not None and classify_posting_state(
            row.posting_sequence, cursors.get(posting_scope_of(row))
        ) == TransactionStatus.POSTED:
            history.append((ensure_utc(row.posted_at), row.amount_cents))
    history.sort(key=lambda entry: entry[0])
    return _SavingsLedger(history, paid_keys, paid_through)


def _end_of_day_balances(history, day_ends):
    """Balance at each (ascending) day end: effects in effect before it."""
    balances = []
    cents = 0
    index = 0
    for day_end in day_ends:
        while index < len(history) and history[index][0] < day_end:
            cents += history[index][1]
            index += 1
        balances.append(Decimal(cents) / 100)
    return balances


def _accrual_floor(class_id, ledger, claimed_at):
    """The instant before which no day accrues for this seat.

    Nothing accrues before the window-keyed start, before the seat's first
    savings effect, before the seat was claimed, or on a day already credited.
    """
    floors = [_class_local_midnight_utc(class_id, WINDOW_KEYED_PAYOUT_START)]
    if ledger.history:
        floors.append(ledger.history[0][0])
    if claimed_at is not None:
        floors.append(ensure_utc(claimed_at))
    if ledger.paid_through is not None:
        floors.append(ledger.paid_through)
    return max(floors)


def _window_days(class_id, policy, window, history, rate_at, accrue_after):
    """One window's days: balance, rate, and compounding marker per day.

    A day ending at or before ``accrue_after`` keeps its place, so compounding
    boundaries stay where they are, but accrues nothing.
    """
    plan = _window_day_plan(
        class_id, _compounding_period(policy), window.start_utc, window.end_utc
    )
    balances = _end_of_day_balances(history, [day_end for day_end, _ in plan])
    return plan, balances, [
        rate_at(day_end) if day_end > accrue_after else None for day_end, _ in plan
    ]


def _window_interest(class_id, policy, window, history, rate_at, accrue_after):
    """Interest credited for one closed window by the daily balance method."""
    plan, balances, rates = _window_days(
        class_id, policy, window, history, rate_at, accrue_after
    )
    days = [
        SavingsAccrualDay(end_of_day_balance=balance, annual_rate=rate, capitalizes=capitalizes)
        for (_day_end, capitalizes), balance, rate in zip(plan, balances, rates)
    ]
    return credit_savings_interest(accrue_daily_interest(
        days=days,
        calculation_type=policy.calculation_type,
        compound_frequency=policy.compound_frequency,
    ))


def apply_savings_interest(seat, *, annual_rate=None, reference_time_utc=None):
    """Credit every closed, unpaid payout window for one seat, oldest first.

    SPEC-ECON-001 §14.1: resolve the class-local boundary, determine which payout
    windows have closed since the last settled one, and credit each exactly once.
    The window is the teacher-configured ``interest_payout_frequency`` — a
    Monday-start class-local week or a class-local calendar month. Interest
    accrues daily on each class-local day's end-of-day balance and is rounded
    once, when the window is credited (§9.2, §5.3). Returns the transactions
    created by this call.
    """
    if not seat:
        return []

    class_id = seat.class_id
    policy = resolve_savings_policy(class_id)
    # Each day accrues at the rate in force that day, so a window can owe
    # interest after the rate is switched off; only a class that has never had
    # a positive rate (or a non-positive override) has nothing to do (§11).
    rate_at, ever_positive = _rate_timeline(class_id, annual_rate)
    if not ever_positive:
        return []

    cadence = (policy.payout_frequency or "monthly").strip().lower()
    now_utc = _resolve(
        class_id, "current_time", reference_time_utc=reference_time_utc
    ).canonical_now_utc

    ledger = _savings_ledger(seat.id, class_id, cadence)
    if not ledger.history:
        return []
    history = list(ledger.history)
    accrue_after = _accrual_floor(class_id, ledger, seat.claimed_at)

    created = []
    window = payout_window_containing(class_id, cadence, accrue_after)
    while window.end_utc <= now_utc:
        key = savings_interest_idempotency_key(class_id, seat.id, window)
        if key not in ledger.paid_keys:
            interest = _window_interest(class_id, policy, window, history, rate_at, accrue_after)
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
                # The credit joins the balance from its window's close, as the
                # ledger will reconstruct it on the next run (§9.2).
                insort(history, (window.end_utc, transaction.amount_cents))
        window = payout_window_containing(class_id, cadence, window.end_utc)
    return created


def forecast_savings(seat_id, class_id, *, months=12, reference_time_utc=None):
    """Read-only savings forecast on the payout job's own terms (SPEC-ECON-001 §10).

    Walks the class-local payout calendar forward from the open window. Days of
    the open window that have already ended use their reconstructed end-of-day
    balance; every later day assumes the balance is left alone. Each window is
    credited exactly as ``apply_savings_interest`` will credit it, so with no
    further activity the forecast is what posts.

    Returns ``policy``, ``next_credit`` (what the open window will credit) and
    ``series`` (``months + 1`` balances: now, then one per class-local month
    from today).
    """
    policy = resolve_savings_policy(class_id)
    rate_at, ever_positive = _rate_timeline(class_id)
    # A rate dated for later is part of the forecast from its effective date, so
    # a class with no rate in force yet can still have interest to project.
    if not ever_positive:
        posted_now = get_posted_balance(seat_id, class_id, "savings")
        return SimpleNamespace(
            policy=policy, next_credit=Decimal("0.00"), series=[posted_now] * (months + 1)
        )

    cadence = (policy.payout_frequency or "monthly").strip().lower()
    now_utc = _resolve(
        class_id, "current_time", reference_time_utc=reference_time_utc
    ).canonical_now_utc
    ledger = _savings_ledger(seat_id, class_id, cadence)
    posted_now = _end_of_day_balances(ledger.history, [now_utc])[0]
    seat = Seat.query.filter_by(id=seat_id, class_id=class_id).one_or_none()
    accrue_after = _accrual_floor(class_id, ledger, seat.claimed_at if seat else None)

    today = _resolve(class_id, "evaluation_day_boundaries", reference_time_utc=now_utc)
    today_start = today.boundary_start_utc
    checkpoints_utc = [
        _resolve(
            class_id,
            "anchored_recurrence_boundary",
            anchor_date=today.boundary_start.date(),
            cadence="month",
            index=month,
            overflow="clamp",
        ).boundary_start_utc
        for month in range(1, months + 1)
    ]
    # The open window always; then every window closing by the last forecast point.
    horizon = checkpoints_utc[-1] if checkpoints_utc else None
    windows = []
    closes = []
    window = payout_window_containing(class_id, cadence, now_utc)
    while not windows or (horizon is not None and window.end_utc <= horizon):
        paid = savings_interest_idempotency_key(class_id, seat_id, window) in ledger.paid_keys
        plan, known, rates = _window_days(
            class_id, policy, window, ledger.history, rate_at, accrue_after
        )
        windows.append([
            ProjectedSavingsDay(
                end_of_day_balance=balance if day_end <= today_start else None,
                annual_rate=None if paid else rate,
                capitalizes=capitalizes,
            )
            for (day_end, capitalizes), balance, rate in zip(plan, known, rates)
        ])
        closes.append(window.end_utc)
        window = payout_window_containing(class_id, cadence, window.end_utc)

    series = project_savings_balances(
        posted_balance=posted_now,
        windows=windows,
        checkpoints=[sum(1 for close in closes if close <= point) for point in checkpoints_utc],
        calculation_type=policy.calculation_type,
        compound_frequency=policy.compound_frequency,
    )
    next_credit = project_savings_balances(
        posted_balance=posted_now,
        windows=windows[:1],
        checkpoints=[1],
        calculation_type=policy.calculation_type,
        compound_frequency=policy.compound_frequency,
    )[1] - series[0]
    return SimpleNamespace(policy=policy, next_credit=next_credit, series=series)


__all__ = [
    "WINDOW_KEYED_PAYOUT_START",
    "apply_savings_interest",
    "forecast_savings",
    "payout_window_containing",
    "resolve_savings_policy",
    "savings_interest_idempotency_key",
]
