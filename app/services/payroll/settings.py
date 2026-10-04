"""The one payroll-settings resolver (operator ruling 2026-09-30).

``payroll_settings`` is the sole payroll authority and is append-only with an
effective date (DOM-POL-001 §VI.2, DOM-POL-001A §V.F). This module is the only
place that queries it: every payroll reader — pricing, settlement, the
scheduler, daily-limit enforcement, estimates, displays, the insurance lost-time
rate, the PROD-PAY-001 correction tool, interpretation — asks it which setting
was in force at an instant. A structural guard
(``tests/guards/payroll_settings_reads.py``) refuses a query anywhere else.

    in force at t  =  greatest effective_date <= t, then latest created_at

A row whose ``effective_date`` is still ahead is *pending*: visible and
immutable, not yet in force. Nothing activates it; time does.

Reads are pure (INV-ARC-007). ``save_payroll_setting`` is the single writer and
never updates a row: a save is an append whose effective date is the next
payroll boundary (DOM-CLASS-003 §VII).
"""

from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db
from app.models import PayrollSettings
from app.utils.canonical_temporal_resolver import ensure_utc, utc_now

# The rate a class with no payroll setting is shown and, for an insurance
# lost-time claim, paid at. A payroll run never uses it: settlement refuses a
# class that has no setting to price with.
DEFAULT_PAY_RATE_PER_MINUTE = Decimal('0.25')
DEFAULT_PAY_RATE_PER_SECOND = DEFAULT_PAY_RATE_PER_MINUTE / Decimal('60')

_UNIT_SECONDS = {'seconds': 1, 'minutes': 60, 'hours': 3600, 'days': 86400}


def _for_class(class_id: str):
    if not class_id:
        raise ValueError("payroll_settings reads require class_id.")
    return PayrollSettings.query.filter(PayrollSettings.class_id == class_id)


def _newest_first(query):
    return query.order_by(
        PayrollSettings.effective_date.desc(),
        PayrollSettings.created_at.desc(),
    )


def payroll_setting_effective_at(class_id: str, instant) -> PayrollSettings | None:
    """The setting in force for ``class_id`` at ``instant``, or None before the first."""
    instant = ensure_utc(instant)
    return _newest_first(
        _for_class(class_id).filter(PayrollSettings.effective_date <= instant)
    ).first()


def payroll_setting_in_force_before(class_id: str, instant) -> PayrollSettings | None:
    """The setting in force immediately before ``instant``.

    A payroll boundary at ``instant`` is where a pending setting takes effect, so
    the setting that governed the cycle closing there is the one in force just
    before it (DOM-ITR-001 §IX reference configuration).
    """
    instant = ensure_utc(instant)
    return _newest_first(
        _for_class(class_id).filter(PayrollSettings.effective_date < instant)
    ).first()


def first_payroll_setting(class_id: str) -> PayrollSettings | None:
    return _for_class(class_id).order_by(
        PayrollSettings.effective_date.asc(), PayrollSettings.created_at.asc()
    ).first()


def payroll_setting_governing_work(class_id: str, closed_at) -> PayrollSettings | None:
    """The setting that prices work closing at ``closed_at`` (DOM-PROD-001 §XV.3).

    Work that closed before the class recorded any setting is priced by its first
    setting: no earlier setting was ever in force, and the first one is in force
    from the moment it is saved.
    """
    return payroll_setting_effective_at(class_id, closed_at) or first_payroll_setting(class_id)


def current_payroll_setting(class_id: str, *, as_of=None) -> PayrollSettings | None:
    """The setting in force now (or at ``as_of``)."""
    return payroll_setting_effective_at(class_id, as_of or utc_now())


def pending_payroll_settings(class_id: str, *, as_of=None) -> list[PayrollSettings]:
    """Settings saved but not yet in force, soonest first.

    For each future effective date only the row that will be in force at that
    date is returned (the latest save wins, DOM-CLASS-003 §VII); a pending row
    superseded before its date stays in history but is not a pending change.
    """
    as_of = ensure_utc(as_of or utc_now())
    rows = (
        _for_class(class_id)
        .filter(PayrollSettings.effective_date > as_of)
        .order_by(PayrollSettings.effective_date.asc(), PayrollSettings.created_at.desc())
        .all()
    )
    winners: dict[datetime, PayrollSettings] = {}
    for row in rows:
        winners.setdefault(ensure_utc(row.effective_date), row)
    return list(winners.values())


def payroll_setting_history(class_id: str) -> list[PayrollSettings]:
    """Every setting the class has recorded, newest effective first."""
    return _newest_first(_for_class(class_id)).all()


def class_has_payroll_settings(class_id: str) -> bool:
    return _for_class(class_id).first() is not None


def payroll_setting_by_uuid(class_id: str, policy_uuid: str) -> PayrollSettings | None:
    """Resolve a frozen reference (DOM-POL-001 §VII) within its class."""
    if not policy_uuid:
        return None
    return _for_class(class_id).filter(PayrollSettings.policy_uuid == policy_uuid).first()


def classes_with_payroll_settings() -> list[str]:
    """Every class that has recorded a payroll setting, for the scheduler."""
    return [
        class_id
        for (class_id,) in (
            db.session.query(PayrollSettings.class_id)
            .distinct()
            .order_by(PayrollSettings.class_id.asc())
            .all()
        )
    ]


def pay_rate_per_minute(setting: PayrollSettings | None) -> Decimal:
    if setting is not None and setting.pay_rate:
        return Decimal(str(setting.pay_rate))
    return DEFAULT_PAY_RATE_PER_MINUTE


def pay_rate_per_second(setting: PayrollSettings | None) -> Decimal:
    if setting is not None and setting.pay_rate:
        return Decimal(str(setting.pay_rate)) / Decimal('60')
    return DEFAULT_PAY_RATE_PER_SECOND


def current_pay_rate_per_second(class_id: str) -> Decimal:
    """The per-second rate of the setting in force now, else the default."""
    return pay_rate_per_second(current_payroll_setting(class_id))


def daily_limit_seconds(setting: PayrollSettings | None) -> int | None:
    """The daily working limit a setting enforces, or None for no limit."""
    if setting is None or not setting.max_time_per_day:
        return None
    unit = _UNIT_SECONDS.get((setting.max_time_per_day_unit or 'hours').strip(), 3600)
    return int(setting.max_time_per_day * unit)


def current_daily_limit_seconds(class_id: str, *, as_of=None) -> int | None:
    return daily_limit_seconds(current_payroll_setting(class_id, as_of=as_of))


def append_payroll_setting(
    *, class_id: str, settings_data: dict, effective_date, created_at
) -> PayrollSettings:
    """Insert one immutable row. The caller decides the effective date."""
    unknown = set(settings_data) - set(PayrollSettings.SETTING_FIELDS)
    if unknown:
        raise ValueError(
            f"Unknown payroll settings field(s): {sorted(unknown)}. "
            "Legal columns are PayrollSettings.SETTING_FIELDS (DOM-POL-001A §V.F)."
        )
    if settings_data.get('first_pay_date') is None:
        raise ValueError("A payroll setting needs a first pay date: it anchors the schedule.")
    if settings_data.get('pay_schedule_type') not in PayrollSettings.PAY_SCHEDULE_TYPES:
        raise ValueError("A payroll schedule is weekly, biweekly or monthly.")
    created_at = ensure_utc(created_at)
    effective_date = ensure_utc(effective_date)
    if effective_date < created_at:
        raise ValueError("A payroll setting cannot take effect before it was recorded.")
    row = PayrollSettings(
        class_id=class_id,
        effective_date=effective_date,
        created_at=created_at,
        **settings_data,
    )
    db.session.add(row)
    db.session.flush()
    return row


def save_payroll_setting(*, class_id: str, settings_data: dict, recorded_at=None) -> PayrollSettings:
    """Record a teacher's payroll settings as a new effective-dated row.

    The first setting a class records is in force at once. Any later one takes
    effect at the class's next payroll boundary, so the open cycle keeps the
    setting its work was done under (DOM-CLASS-003 §VII, DOM-PROD-001 §XV.3).
    Fields the submission omits are carried from the setting it will follow, so
    a partial post still yields a complete row. Runs inside the caller's FEAT;
    never commits.
    """
    from app.services.payroll.schedule import effective_date_for_new_setting

    recorded_at = ensure_utc(recorded_at or utc_now())
    effective_date = effective_date_for_new_setting(class_id, recorded_at)
    predecessor = payroll_setting_effective_at(class_id, effective_date)
    data = {}
    if predecessor is not None:
        data = {field: getattr(predecessor, field) for field in PayrollSettings.SETTING_FIELDS}
    data.update(settings_data)
    return append_payroll_setting(
        class_id=class_id,
        settings_data=data,
        effective_date=effective_date,
        created_at=recorded_at,
    )


def destroy_payroll_settings_for_classes(class_ids) -> None:
    """Remove the classes' settings as part of class-universe destruction only.

    ``payroll_settings`` refuses DELETE unless the transaction has declared the
    destruction (``cth.class_universe_destroying``, FEAT-CLASS-006 /
    FEAT-IDEN-007); outside that, the trigger raises. ``class_ids`` is a list or
    a SELECT of class ids.
    """
    PayrollSettings.query.filter(
        PayrollSettings.class_id.in_(class_ids)
    ).delete(synchronize_session=False)


# DOM-POL-001 §X.1: immutable observations only; no policy admission.


@dataclass(frozen=True)
class HistoricalPayrollSettingInput:
    class_id: str
    policy_locator: str
    effective_at: object
    created_at: object
    rate_per_minute: str
    legacy_rate_per_minute: str | None = None


def get_historical_payroll_setting_inputs(*, ctx, class_id, limit=500):
    """Bounded retained settings for FEAT-PROD-006 candidate reconstruction."""
    if (not class_id or not getattr(ctx,'seat_id',None) or not getattr(ctx,'user_id',None)
            or getattr(ctx, 'class_id', None) != class_id
            or getattr(ctx, 'actor_role', None) != 'teacher'):
        raise ValueError('UNAUTHORIZED_SCOPE')
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError('INVALID_INPUT')
    with db.session.no_autoflush:
        rows = _for_class(class_id).order_by(PayrollSettings.effective_date.asc(),
            PayrollSettings.created_at.asc()).limit(limit + 1).all()
    if len(rows) > limit:
        raise ValueError('EVIDENCE_LIMIT_EXCEEDED')
    return tuple(HistoricalPayrollSettingInput(row.class_id,row.policy_uuid,
        ensure_utc(row.effective_date),ensure_utc(row.created_at),str(row.pay_rate),
        str(row.pay_rate or Decimal('0.25'))) for row in rows)
