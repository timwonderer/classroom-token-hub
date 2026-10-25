"""Rent successor due dates are stepped through the canonical temporal resolver.

SPEC-TIME-001: class-local date arithmetic (days, weeks, months) goes through
``shift_calendar_days`` / ``anchored_recurrence_boundary``, never raw ``timedelta``.
"""

from datetime import date
from types import SimpleNamespace

from app.services.rent_schedule_service import advance_due_date
from tests.helpers.classroom_initializer import initialize


def _settings(**kw):
    base = dict(
        frequency_type="monthly", due_day_of_month=None,
        custom_frequency_value=None, custom_frequency_unit=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_advance_due_date_steps_days_weeks_and_months(app):
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        ctx = SimpleNamespace(class_id=classroom.class_id)

        assert advance_due_date(_settings(frequency_type="daily"), date(2026, 3, 31), context=ctx) == date(2026, 4, 1)
        assert advance_due_date(_settings(frequency_type="weekly"), date(2026, 12, 28), context=ctx) == date(2027, 1, 4)
        # Monthly clamps to the month end, then re-anchors to the configured due day.
        assert advance_due_date(_settings(due_day_of_month=31), date(2026, 1, 31), context=ctx) == date(2026, 2, 28)
        assert advance_due_date(_settings(due_day_of_month=31), date(2026, 2, 28), context=ctx) == date(2026, 3, 31)
        custom = _settings(frequency_type="custom", custom_frequency_value=2)
        custom.custom_frequency_unit = "weeks"
        assert advance_due_date(custom, date(2026, 1, 1), context=ctx) == date(2026, 1, 15)


def test_custom_months_derive_from_the_anchor_not_a_clamped_intermediate(app):
    """Jan 31 + 2 months is Mar 31; stepping via a clamped Feb 28 used to give Mar 28."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        ctx = SimpleNamespace(class_id=classroom.class_id)
        custom = _settings(frequency_type="custom", custom_frequency_value=2, custom_frequency_unit="months")
        assert advance_due_date(custom, date(2026, 1, 31), context=ctx) == date(2026, 3, 31)
