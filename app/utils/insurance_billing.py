"""Helpers for insurance billing cadence and legacy enrollment reset behavior."""

from datetime import datetime, timedelta, timezone

from app.utils.time import ensure_utc


# Launch date for recurring billing enforcement from FEAT-INS-002.
# Pre-launch enrollments get one fresh billing cycle when enforcement first runs.
INSURANCE_BILLING_LAUNCH_CUTOFF = datetime(2026, 4, 19, tzinfo=timezone.utc)


def insurance_next_payment_due(now_utc, charge_frequency):
    """Return the next premium due date for the given billing frequency."""
    frequency = (charge_frequency or 'monthly').lower()
    if frequency == 'weekly':
        return now_utc + timedelta(days=7)
    if frequency == 'biweekly':
        return now_utc + timedelta(days=14)
    if frequency == 'semester':
        return now_utc + timedelta(days=7 * 16)
    return now_utc + timedelta(days=28)


def should_reset_legacy_billing_cycle(enrollment, now_utc):
    """Return True when an active enrollment predates recurring billing launch."""
    if not enrollment or enrollment.status != 'active':
        return False

    purchase_date = ensure_utc(enrollment.purchase_date)
    if not purchase_date:
        return False

    if purchase_date >= INSURANCE_BILLING_LAUNCH_CUTOFF:
        return False

    next_due = ensure_utc(enrollment.next_payment_due)
    return next_due is None or next_due <= now_utc
