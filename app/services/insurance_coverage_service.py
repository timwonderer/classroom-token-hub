"""Insurance coverage reads — Store and Entitlements (DOM-STORE-001 §VIII.E.1).

An insurance entitlement's premium lineage (``DOM-OBL-001`` §II.B) defines its
coverage periods, and its usability at a reference time is derived — never
stored. This module is the single place Store answers:

- which premium lineage belongs to an entitlement (``internal_ref`` derives from
  the ``entitlement_id`` alone, never from a purchase command's key);
- where a coverage boundary falls (anchored recurrence from the purchase's
  class-local date, ``SPEC-TIME-001`` §IX.12);
- which coverage period contains a reference time;
- whether the entitlement is usable at a reference time.

Store consumes the Obligations answer as a boolean
(``are_required_obligations_satisfied``); it does not inspect obligation tables
or reconstruct payment status, and it persists no ``payment_current`` /
``SUSPENDED`` flag (FEAT-STOR-007 §X). Pure reads (INV-ARC-007).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from types import SimpleNamespace

from app.extensions import db
from app.models import BillCycle, EntitlementEvent
from app.services import obligations_service
from app.services.policy_reference_service import (
    INSURANCE_MONTHLY_OVERFLOW,
    insurance_cadence,
)
from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION,
    canonical_temporal_resolver,
    ensure_utc,
)


PREMIUM_LINEAGE_PREFIX = "insurance:"
_TERMINAL_EVENT_TYPES = ("EXPIRED", "REVOKED")


def premium_lineage_ref(entitlement_id: str) -> str:
    """The premium lineage (``internal_ref``) of one insurance entitlement (§II.B)."""
    if not entitlement_id:
        raise ValueError("premium_lineage_ref requires an entitlement_id")
    return f"{PREMIUM_LINEAGE_PREFIX}{entitlement_id}"


def entitlement_id_for_premium_lineage(internal_ref: str | None) -> str | None:
    """The entitlement a premium lineage belongs to, or ``None`` for another lineage.

    Store authored the lineage key, so Store may read it back; Obligations
    treats it as opaque.
    """
    if not internal_ref or not internal_ref.startswith(PREMIUM_LINEAGE_PREFIX):
        return None
    entitlement_id = internal_ref[len(PREMIUM_LINEAGE_PREFIX):]
    return entitlement_id or None


def _ctx(class_id: str) -> SimpleNamespace:
    return SimpleNamespace(class_id=class_id)


def class_local_date(class_id: str, instant_utc: datetime) -> date:
    """The class-local calendar date of an instant (the cadence anchor for a purchase)."""
    return canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=_ctx(class_id),
        primitive="current_evaluation_day",
        reference_time_utc=ensure_utc(instant_utc),
    ).evaluation_date


def coverage_boundary(
    class_id: str,
    *,
    anchor_date: date,
    charge_frequency: str,
    index: int,
) -> datetime:
    """Coverage boundary ``index`` of a lineage anchored on ``anchor_date`` (UTC).

    FEAT-STOR-007 §IV: class-local midnight of
    ``anchored_recurrence_boundary(anchor, cadence, index, roll_forward)``.
    Every boundary is derived from the anchor, never from a previous boundary.
    Period ``n`` (``n ≥ 1``) is ``[boundary(n − 1), boundary(n))``, except that
    period 1 begins at the purchase instant rather than at midnight.
    """
    cadence = insurance_cadence(charge_frequency)
    extra = {"overflow": INSURANCE_MONTHLY_OVERFLOW} if cadence == "month" else {}
    return canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=_ctx(class_id),
        primitive="anchored_recurrence_boundary",
        anchor_date=anchor_date,
        cadence=cadence,
        index=index,
        **extra,
    ).boundary_start_utc


def get_first_coverage_cycle(class_id: str, entitlement_id: str) -> BillCycle | None:
    """Cycle 1 of the entitlement's premium lineage: its start is the purchase instant."""
    return (
        db.session.query(BillCycle)
        .filter_by(
            class_id=class_id,
            internal_ref=premium_lineage_ref(entitlement_id),
            cycle_number=1,
        )
        .one_or_none()
    )


def get_cadence_anchor(class_id: str, entitlement_id: str) -> date | None:
    """The class-local date of purchase, which anchors every later boundary."""
    first = get_first_coverage_cycle(class_id, entitlement_id)
    if first is None:
        return None
    return class_local_date(class_id, first.cycle_boundary_at)


@dataclass(frozen=True)
class CoveragePeriod:
    """One coverage period ``[start_utc, end_utc)`` of an insurance entitlement."""
    bill_cycle_id: int
    cycle_number: int
    start_utc: datetime
    end_utc: datetime


def get_coverage_period(
    class_id: str,
    entitlement_id: str,
    *,
    reference_time_utc: datetime | None = None,
) -> CoveragePeriod | None:
    """The coverage period containing the reference time, if one is in force.

    It is the lineage's current bill cycle (``DOM-OBL-001`` §V.7): never the
    latest cycle, and never a period at or after the lineage's termination
    instant.
    """
    cycle = obligations_service.get_current_bill_cycle(
        class_id,
        premium_lineage_ref(entitlement_id),
        reference_time_utc=reference_time_utc,
    )
    if cycle is None:
        return None
    return CoveragePeriod(
        bill_cycle_id=cycle.id,
        cycle_number=cycle.cycle_number,
        start_utc=ensure_utc(cycle.cycle_boundary_at),
        end_utc=ensure_utc(cycle.next_assessment_at),
    )


def get_insurance_grant(class_id: str, entitlement_id: str) -> EntitlementEvent | None:
    """The GRANTED event of one insurance entitlement in the class."""
    return (
        db.session.query(EntitlementEvent)
        .filter_by(
            class_id=class_id,
            entitlement_id=entitlement_id,
            entitlement_type="INSURANCE",
            event_type="GRANTED",
        )
        .first()
    )


def get_terminal_event(class_id: str, entitlement_id: str) -> EntitlementEvent | None:
    """The EXPIRED or REVOKED event of an entitlement, whenever it takes effect."""
    return (
        db.session.query(EntitlementEvent)
        .filter(
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.entitlement_id == entitlement_id,
            EntitlementEvent.event_type.in_(_TERMINAL_EVENT_TYPES),
        )
        .first()
    )


def _at_or_before(class_id: str, candidate: datetime, reference: datetime) -> bool:
    return not canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=_ctx(class_id),
        primitive="later_than",
        reference_time_utc=reference,
        candidate=candidate,
        reference=reference,
    ).is_later


def _reference_now(class_id: str, reference_time_utc: datetime | None) -> datetime:
    return canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=_ctx(class_id),
        primitive="current_time",
        reference_time_utc=reference_time_utc,
    ).canonical_now_utc


@dataclass(frozen=True)
class InsuranceUsability:
    """Why an insurance entitlement is or is not usable at a reference time."""
    usable: bool
    reason: str | None = None  # NOT_GRANTED | TERMINATED | NO_COVERAGE_PERIOD | PREMIUM_UNPAID
    terminal_event: EntitlementEvent | None = None
    period: CoveragePeriod | None = None


def evaluate_insurance_usability(
    class_id: str,
    entitlement_id: str,
    *,
    reference_time_utc: datetime | None = None,
) -> InsuranceUsability:
    """Whether an insurance entitlement is usable at the reference time (§VIII.E.1).

    Usable only when: it was granted at or before the reference time; no
    ``EXPIRED`` or ``REVOKED`` takes effect at or before it; a coverage period
    of its lineage contains it; and Obligations reports the lineage's required
    obligations satisfied at it (facts recorded at or before the reference time
    only, so a late payment restores usability prospectively and never for the
    gated interval before it).
    """
    reference = _reference_now(class_id, reference_time_utc)
    grant = get_insurance_grant(class_id, entitlement_id)
    if grant is None or not _at_or_before(class_id, grant.timestamp, reference):
        return InsuranceUsability(usable=False, reason="NOT_GRANTED")

    terminal = get_terminal_event(class_id, entitlement_id)
    if terminal is not None and _at_or_before(class_id, terminal.timestamp, reference):
        return InsuranceUsability(usable=False, reason="TERMINATED", terminal_event=terminal)

    period = get_coverage_period(class_id, entitlement_id, reference_time_utc=reference)
    if period is None:
        return InsuranceUsability(usable=False, reason="NO_COVERAGE_PERIOD")

    if not obligations_service.are_required_obligations_satisfied(
        class_id, premium_lineage_ref(entitlement_id), reference_time_utc=reference
    ):
        return InsuranceUsability(usable=False, reason="PREMIUM_UNPAID", period=period)
    return InsuranceUsability(usable=True, period=period)


def is_insurance_usable(
    class_id: str,
    entitlement_id: str,
    *,
    reference_time_utc: datetime | None = None,
) -> bool:
    """Boolean form of :func:`evaluate_insurance_usability`."""
    return evaluate_insurance_usability(
        class_id, entitlement_id, reference_time_utc=reference_time_utc
    ).usable


def are_premiums_current(
    class_id: str,
    entitlement_id: str,
    *,
    reference_time_utc: datetime | None = None,
) -> bool:
    """Whether every premium due so far on the entitlement's lineage is satisfied.

    Display read for teacher/student surfaces; the Obligations answer, never a
    cached flag.
    """
    return obligations_service.are_required_obligations_satisfied(
        class_id,
        premium_lineage_ref(entitlement_id),
        reference_time_utc=reference_time_utc,
    )
