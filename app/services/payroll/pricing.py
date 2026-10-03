"""Price a seat's attendance by the payroll setting in force (DOM-PROD-001 §XV.3).

Operator ruling 2026-09-30: a payroll change saved mid-cycle must not reprice
work done under the old setting. Each session a run settles is therefore priced
by the ``payroll_settings`` row in force when that session closed, never by the
row in force when the run happens. A run whose sessions fall under several
settings prices each setting's share separately; the shares are recorded in the
payroll event's ``summary_json`` so the amount is reproducible from recorded
inputs (INV-CORE-000 §III.3), and the amount itself is not stored (§VIII.3).

The payroll run (FEAT-PROD-003) and every estimate shown before it — the
teacher's payroll page, the student's tap response — price through this module,
so a preview and the payout cannot disagree. Pure reads (INV-ARC-007).

Pricing is exact: elapsed seconds × rate, quantized to the cent. There is no
time rounding (operator ruling 2026-09-30; DOM-PROD-001 §XV.3).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN

from app.services.attendance_service import (
    calculate_seat_payroll_intervals,
    elapsed_attendance_seconds,
)
from app.services.payroll.settings import (
    DEFAULT_PAY_RATE_PER_MINUTE,
    payroll_setting_governing_work,
)
from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION,
    canonical_temporal_resolver,
    ensure_utc,
)

CENT = Decimal("0.01")
SUMMARY_PRICING_KEY = "pricing"


class NoPayrollSettingError(LookupError):
    """Attendance cannot be priced: the class has never recorded a payroll setting."""


@dataclass(frozen=True)
class SettingShare:
    """The part of a settlement one payroll setting priced."""

    policy_uuid: str | None
    pay_rate_per_minute: Decimal
    seconds: int
    last_closed_at: object
    intervals: tuple = ()

    @property
    def amount(self) -> Decimal:
        return amount_for(self.seconds, self.pay_rate_per_minute)

    def as_summary(self) -> dict:
        # Inputs only: the amount follows from them and is not stored.
        return {
            "policy_uuid": self.policy_uuid,
            "seconds": self.seconds,
            "pay_rate_per_minute": str(self.pay_rate_per_minute),
            "intervals": [i.as_evidence() for i in self.intervals],
        }


@dataclass(frozen=True)
class PricedAttendance:
    shares: tuple

    @property
    def seconds(self) -> int:
        return sum(share.seconds for share in self.shares)

    @property
    def amount(self) -> Decimal:
        return sum((share.amount for share in self.shares), Decimal("0.00"))

    @property
    def policy_uuid(self) -> str | None:
        """The setting that governed the latest-closing session (DOM-PROD-001 §XI.3)."""
        if not self.shares:
            return None
        return max(self.shares, key=lambda share: share.last_closed_at).policy_uuid

    def summary(self) -> list[dict]:
        return [share.as_summary() for share in self.shares]


def amount_for(seconds: int, pay_rate_per_minute) -> Decimal:
    """Money for ``seconds`` at a per-minute rate, to the cent."""
    return (Decimal(seconds) * Decimal(str(pay_rate_per_minute)) / Decimal("60")).quantize(
        CENT, rounding=ROUND_HALF_EVEN
    )


def amount_from_summary(pricing: list[dict]) -> Decimal:
    """Reproduce a payroll event's amount from its recorded pricing inputs."""
    return sum(
        (amount_for(int(entry["seconds"]), Decimal(entry["pay_rate_per_minute"])) for entry in pricing),
        Decimal("0.00"),
    )


def _price_intervals(class_id: str, ctx, intervals, *, estimate: bool = False) -> PricedAttendance:
    """Group ``(start, closed_at)`` intervals by the setting in force at close.

    A class with no setting cannot be paid, so settlement raises. An estimate
    for such a class is shown at the default rate, as it always was.
    """
    groups: dict[str | None, list] = {}
    rates: dict[str | None, Decimal] = {}
    for interval in intervals:
        start, closed_at = interval
        setting = payroll_setting_governing_work(class_id, closed_at)
        if setting is None:
            if not estimate:
                raise NoPayrollSettingError(
                    f"Class {class_id} has no payroll setting to price attendance with."
                )
            rates[None] = DEFAULT_PAY_RATE_PER_MINUTE
            groups.setdefault(None, []).append(interval)
            continue
        rates[setting.policy_uuid] = Decimal(str(setting.pay_rate))
        groups.setdefault(setting.policy_uuid, []).append(interval)
    shares = []
    for policy_uuid, grouped in groups.items():
        seconds = elapsed_attendance_seconds(ctx, grouped)
        if seconds <= 0:
            continue
        shares.append(SettingShare(
            policy_uuid=policy_uuid,
            pay_rate_per_minute=rates[policy_uuid],
            seconds=int(seconds),
            last_closed_at=max(ensure_utc(end) for _start, end in grouped),
            intervals=tuple(i for i in grouped if hasattr(i, "as_evidence")),
        ))
    shares.sort(key=lambda share: share.last_closed_at)
    return PricedAttendance(shares=tuple(shares))


def price_payable_attendance(seat_id: int, class_id: str, *, ctx, as_of_utc) -> PricedAttendance:
    """What a payroll run at ``as_of_utc`` pays the seat: closed, unpaid work."""
    intervals = calculate_seat_payroll_intervals(seat_id, class_id, ctx=ctx, as_of_utc=as_of_utc)
    if intervals.unprovable:
        raise ValueError("Historical partial settlement has no provable interval membership.")
    return _price_intervals(class_id, ctx, intervals.payable)


def _now(ctx, as_of_utc):
    if as_of_utc is not None:
        return as_of_utc
    return canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="current_time",
    ).canonical_now_utc


def estimate_payable_amount(seat_id: int, class_id: str, *, ctx, as_of_utc=None) -> Decimal:
    """What a payroll run now would pay the seat (the teacher's estimate)."""
    as_of_utc = _now(ctx, as_of_utc)
    intervals = calculate_seat_payroll_intervals(seat_id, class_id, ctx=ctx, as_of_utc=as_of_utc)
    return _price_intervals(class_id, ctx, intervals.payable, estimate=True).amount


def estimate_unpaid_amount(seat_id: int, class_id: str, *, ctx, as_of_utc=None) -> Decimal:
    """Everything not yet paid, the open session priced as if it closed now.

    An estimate, not a settlement: the open session is paid by the first run
    after it closes, at the setting in force then.
    """
    as_of_utc = _now(ctx, as_of_utc)
    intervals = calculate_seat_payroll_intervals(seat_id, class_id, ctx=ctx, as_of_utc=as_of_utc)
    return _price_intervals(
        class_id, ctx, intervals.payable + intervals.in_progress, estimate=True
    ).amount
