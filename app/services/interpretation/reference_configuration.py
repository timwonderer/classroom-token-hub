"""Frozen ``reference_configuration`` capture for cycle materialization (DOM-ITR-001 §IX §VII).

At the closed-cycle boundary the materialization writer freezes a **versioned,
immutable informational projection** of the economic configuration that governed
the cycle, so a materialized ``interpretation_cycle_record`` is self-describing and
is never reinterpreted against later configuration. This module builds that
projection from authoritative CLASS/economic reads only.

The projection is explicitly:
* **informational** — never executable CLASS state; nothing reads it to make an
  economic decision (§IX),
* **bound to the closed cycle** — from ``schema_version`` 2 the pay rate and the
  ``policy`` block name the ``payroll_settings`` row in force just before the
  cycle's closing boundary (operator ruling 2026-09-30; DOM-ITR-001 §IX), not
  a row of the legacy ``policy_versions`` table,
* **not a cross-domain FK** — ``policy.policy_uuid`` / ``policy.version`` are
  informational lineage strings (INV-ARC-021 §V.7),
* **versioned** via its own ``schema_version`` so the Economic Engine can evolve
  without churning this table.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.services.class_configuration_query_service import resolve_expected_weekly_hours
from app.services.payroll.settings import payroll_setting_in_force_before
from app.utils.canonical_temporal_resolver import utc_now

# Version of the reference_configuration projection shape (independent of the
# observations_json schema_version and of SPEC-ITR-001's version).
REFERENCE_CONFIGURATION_SCHEMA_VERSION = 2


def _money(value) -> str | None:
    """Two-place canonical decimal string, or ``None`` when unset."""
    if value is None:
        return None
    return f"{Decimal(str(value)).quantize(Decimal('0.01'))}"


def _num(value) -> str | None:
    """Normalized canonical decimal string, or ``None`` when unset."""
    if value is None:
        return None
    return str(Decimal(str(value)).normalize())


def capture_reference_configuration(class_id: str, *, cycle_completed_at=None) -> dict[str, Any]:
    """Freeze the governing economic reference values for ``class_id`` (§IX).

    The payroll setting captured is the one in force just before
    ``cycle_completed_at`` (default now): a setting saved during the cycle takes
    effect at its closing boundary, so it governs the next cycle, not this one.

    Deterministic for stable configuration: two captures over unchanged
    configuration produce an identical dict, which is what makes idempotent replay
    of a materialization safe. All numeric values are canonical decimal **strings**
    (or ``None`` when the input is unconfigured — an honest absence, not zero).
    """
    payroll = payroll_setting_in_force_before(class_id, cycle_completed_at or utc_now())
    hourly_pay_rate = None
    if payroll is not None and payroll.pay_rate is not None:
        # pay_rate is stored as $/minute; the CWI reference uses $/hour.
        hourly_pay_rate = Decimal(str(payroll.pay_rate)) * 60

    expected_weekly_hours = resolve_expected_weekly_hours(class_id)
    cwi = None
    if hourly_pay_rate is not None and expected_weekly_hours is not None:
        cwi = hourly_pay_rate * Decimal(str(expected_weekly_hours))

    return {
        "schema_version": REFERENCE_CONFIGURATION_SCHEMA_VERSION,
        "economic_engine": {
            "cwi": _money(cwi),
            "expected_weekly_hours": _num(expected_weekly_hours),
            "hourly_pay_rate": _money(hourly_pay_rate),
        },
        "policy": {
            "policy_uuid": payroll.policy_uuid if payroll else None,
            "version": payroll.effective_date.isoformat() if payroll else None,
        },
    }
