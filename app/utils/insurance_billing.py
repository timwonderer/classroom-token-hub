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
    """Return True when an active enrollment predates recurring billing launch.

    Designed to be a one-time gate: once the cycle is advanced post-launch the
    enrollment will no longer qualify, preventing repeated free-cycle grants on
    every subsequent billing run.
    """
    if not enrollment or enrollment.status != 'active':
        return False

    purchase_date = ensure_utc(enrollment.purchase_date)
    if not purchase_date:
        return False

    if purchase_date >= INSURANCE_BILLING_LAUNCH_CUTOFF:
        return False

    next_due = ensure_utc(enrollment.next_payment_due)

    if next_due is None:
        return True

    if next_due > now_utc:
        return False

    # Only reset when the due date itself is pre-launch, OR when the enrollment
    # has never had a post-launch payment (last_payment_date is still pre-cutoff).
    # This prevents re-resetting once the billing cycle has been advanced past the
    # cutoff via a normal payment or prior reset.
    last_payment_date = ensure_utc(getattr(enrollment, 'last_payment_date', None))
    return (
        next_due < INSURANCE_BILLING_LAUNCH_CUTOFF
        or (
            last_payment_date is not None
            and last_payment_date < INSURANCE_BILLING_LAUNCH_CUTOFF
        )
    )
