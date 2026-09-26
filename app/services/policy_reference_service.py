"""Policies reads that other domains consume by ``policy_uuid`` (DOM-POL-001 §VII).

A downstream fact frozen by reference resolves its terms from the exact
immutable policy version it carries. These reads take that ``policy_uuid`` and
answer one question each, so a consumer never opens a policy-family table or
branches on the family (DOM-POL-001A §V.E).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db
from app.models import InsurancePolicy, RentSettings
from app.utils.canonical_temporal_resolver import (
    SYSTEM_LEVEL_EVALUATION,
    canonical_temporal_resolver,
)


class PolicyReferenceNotFound(LookupError):
    """No policy version with this ``policy_uuid`` exists in the class."""


# Insurance recurring billing terms (DOM-POL-001A §V.E).
ACCUMULATE = "ACCUMULATE"
CANCEL_AFTER_X_DAYS = "CANCEL_AFTER_X_DAYS"
NONPAYMENT_MODES = (ACCUMULATE, CANCEL_AFTER_X_DAYS)

# charge_frequency → anchored-recurrence cadence (SPEC-TIME-001 §IX.12). Monthly
# recurrence rolls forward when the anchor day does not exist; it never clamps.
_INSURANCE_CADENCE = {"WEEKLY": "week", "MONTHLY": "month"}
INSURANCE_MONTHLY_OVERFLOW = "roll_forward"


def insurance_cadence(charge_frequency) -> str:
    """The recurrence cadence (``week`` | ``month``) of an insurance charge frequency."""
    cadence = _INSURANCE_CADENCE.get(str(charge_frequency or "").strip().upper())
    if cadence is None:
        raise ValueError(f"unsupported insurance charge_frequency: {charge_frequency!r}")
    return cadence


def insurance_recurring_terms_violation(
    *,
    charge_frequency,
    bill_preview_days,
    nonpayment_mode,
    cancel_after_days,
) -> str | None:
    """Why a set of insurance recurring terms is unlawful, or ``None`` if lawful.

    DOM-POL-001A §V.E: ``0 < bill_preview_days < minimum_period_duration(cadence)``
    (validated against the calendar through the resolver, never a copied
    constant); ``nonpayment_mode`` is ``ACCUMULATE`` or ``CANCEL_AFTER_X_DAYS``;
    ``cancel_after_days`` is required and positive when the mode is
    ``CANCEL_AFTER_X_DAYS`` and absent otherwise. Pure: reads nothing.
    """
    try:
        cadence = insurance_cadence(charge_frequency)
    except ValueError as exc:
        return str(exc)

    if bill_preview_days is None or isinstance(bill_preview_days, bool):
        return "bill_preview_days is required"
    try:
        preview = int(bill_preview_days)
    except (TypeError, ValueError):
        return "bill_preview_days must be a whole number"
    minimum = canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION,
        primitive="minimum_period_duration",
        cadence=cadence,
    ).minimum_calendar_days
    if not 0 < preview < minimum:
        return (
            f"bill_preview_days must be greater than 0 and less than {minimum} "
            f"(the shortest {cadence}ly period)"
        )

    mode = str(nonpayment_mode or "").strip().upper()
    if mode not in NONPAYMENT_MODES:
        return f"nonpayment_mode must be one of {list(NONPAYMENT_MODES)}"
    if mode == CANCEL_AFTER_X_DAYS:
        if cancel_after_days is None or isinstance(cancel_after_days, bool):
            return "cancel_after_days is required when nonpayment_mode is CANCEL_AFTER_X_DAYS"
        try:
            days = int(cancel_after_days)
        except (TypeError, ValueError):
            return "cancel_after_days must be a whole number"
        if days <= 0:
            return "cancel_after_days must be greater than 0"
    elif cancel_after_days is not None:
        return "cancel_after_days is only allowed when nonpayment_mode is CANCEL_AFTER_X_DAYS"
    return None


@dataclass(frozen=True)
class InsuranceRecurringTerms:
    """The recurring terms frozen on one insurance policy version (DOM-POL-001A §V.E)."""
    policy_uuid: str
    premium: Decimal
    charge_frequency: str
    cadence: str  # week | month
    bill_preview_days: int
    nonpayment_mode: str
    cancel_after_days: int | None


def get_insurance_recurring_terms(policy_uuid: str, *, class_id: str) -> InsuranceRecurringTerms:
    """The recurring terms of the exact insurance version ``policy_uuid``.

    Never the family's current row: a later submission changes the terms only
    for entitlements purchased under its own ``policy_uuid``. Raises
    ``PolicyReferenceNotFound`` when the version is absent from the class, and
    ``ValueError`` when the version carries no lawful recurring terms.
    """
    insurance = (
        db.session.query(InsurancePolicy)
        .filter_by(policy_uuid=policy_uuid, class_id=class_id)
        .one_or_none()
    )
    if insurance is None:
        raise PolicyReferenceNotFound(
            f"no insurance policy version {policy_uuid!r} in class {class_id!r}"
        )
    violation = insurance_recurring_terms_violation(
        charge_frequency=insurance.charge_frequency,
        bill_preview_days=insurance.bill_preview_days,
        nonpayment_mode=insurance.nonpayment_mode,
        cancel_after_days=insurance.cancel_after_days,
    )
    if violation is not None:
        raise ValueError(f"insurance policy {policy_uuid!r}: {violation}")
    return InsuranceRecurringTerms(
        policy_uuid=insurance.policy_uuid,
        premium=Decimal(str(insurance.premium)),
        charge_frequency=insurance.charge_frequency,
        cadence=insurance_cadence(insurance.charge_frequency),
        bill_preview_days=int(insurance.bill_preview_days),
        nonpayment_mode=str(insurance.nonpayment_mode).strip().upper(),
        cancel_after_days=(
            int(insurance.cancel_after_days) if insurance.cancel_after_days is not None else None
        ),
    )


def get_bill_preview_days(policy_uuid: str, *, class_id: str) -> int:
    """The bill preview interval, in class-local calendar days, of one policy version.

    It is the interval before a period's coverage boundary at which that
    period's obligation is assessed and becomes payable (DOM-OBL-001 §V.7).
    ``0`` means the obligation is assessed at the boundary itself.

    Resolves the exact version identified by ``policy_uuid``, never a newer or
    active row of the same family. Raises ``PolicyReferenceNotFound`` when no
    version with that ``policy_uuid`` exists in the class.
    """
    rent = (
        db.session.query(RentSettings)
        .filter_by(policy_uuid=policy_uuid, class_id=class_id)
        .one_or_none()
    )
    if rent is not None:
        if not rent.bill_preview_enabled:
            return 0
        return max(0, int(rent.bill_preview_days or 0))

    insurance = (
        db.session.query(InsurancePolicy)
        .filter_by(policy_uuid=policy_uuid, class_id=class_id)
        .one_or_none()
    )
    if insurance is not None:
        return max(0, int(insurance.bill_preview_days or 0))

    raise PolicyReferenceNotFound(
        f"no policy version {policy_uuid!r} in class {class_id!r}"
    )
