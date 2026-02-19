
import unittest
from datetime import datetime, timezone
from app.routes.student import _calculate_rent_deadlines, _calculate_rent_timeline

# Mocking the settings object
class MockSettings:
    def __init__(self, frequency_type, first_rent_due_date, grace_period_days=3,
                 custom_frequency_value=None, custom_frequency_unit=None, due_day_of_month=1,
                 bill_preview_enabled=False, bill_preview_days=7):
        self.frequency_type = frequency_type
        self.first_rent_due_date = first_rent_due_date
        self.grace_period_days = grace_period_days
        self.custom_frequency_value = custom_frequency_value
        self.custom_frequency_unit = custom_frequency_unit
        self.due_day_of_month = due_day_of_month
        self.bill_preview_enabled = bill_preview_enabled
        self.bill_preview_days = bill_preview_days

class TestRentDeadlines(unittest.TestCase):
    def test_weekly_frequency(self):
        # Start Jan 1 2024 (Monday). Weekly.
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        settings = MockSettings('weekly', start)

        # Check on Jan 3 (Wed). Should be Jan 1.
        ref = datetime(2024, 1, 3, tzinfo=timezone.utc)
        due, grace = _calculate_rent_deadlines(settings, ref)
        self.assertEqual(due, datetime(2024, 1, 1, tzinfo=timezone.utc))

        # Check on Jan 8 (Mon). Should be Jan 8.
        ref = datetime(2024, 1, 8, tzinfo=timezone.utc)
        due, grace = _calculate_rent_deadlines(settings, ref)
        self.assertEqual(due, datetime(2024, 1, 8, tzinfo=timezone.utc))

        # Check on Jan 14 (Sun). Should be Jan 8.
        ref = datetime(2024, 1, 14, tzinfo=timezone.utc)
        due, grace = _calculate_rent_deadlines(settings, ref)
        self.assertEqual(due, datetime(2024, 1, 8, tzinfo=timezone.utc))

    def test_daily_frequency(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        settings = MockSettings('daily', start)

        ref = datetime(2024, 1, 3, tzinfo=timezone.utc)
        due, grace = _calculate_rent_deadlines(settings, ref)
        self.assertEqual(due, datetime(2024, 1, 3, tzinfo=timezone.utc))

    def test_custom_days(self):
        # Every 3 days. Jan 1, Jan 4, Jan 7...
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        settings = MockSettings('custom', start, custom_frequency_value=3, custom_frequency_unit='days')

        # Jan 2 -> Jan 1
        ref = datetime(2024, 1, 2, tzinfo=timezone.utc)
        due, grace = _calculate_rent_deadlines(settings, ref)
        self.assertEqual(due, datetime(2024, 1, 1, tzinfo=timezone.utc))

        # Jan 4 -> Jan 4
        ref = datetime(2024, 1, 4, tzinfo=timezone.utc)
        due, grace = _calculate_rent_deadlines(settings, ref)
        self.assertEqual(due, datetime(2024, 1, 4, tzinfo=timezone.utc))

    def test_custom_months(self):
        # Every 2 months. Jan 15, Mar 15, May 15...
        start = datetime(2024, 1, 15, tzinfo=timezone.utc)
        settings = MockSettings('custom', start, custom_frequency_value=2, custom_frequency_unit='months')

        # Feb 1 -> Jan 15
        ref = datetime(2024, 2, 1, tzinfo=timezone.utc)
        due, grace = _calculate_rent_deadlines(settings, ref)
        self.assertEqual(due, datetime(2024, 1, 15, tzinfo=timezone.utc))

        # Mar 1 -> Mar 15
        ref = datetime(2024, 3, 1, tzinfo=timezone.utc)
        due, grace = _calculate_rent_deadlines(settings, ref)
        self.assertEqual(due, datetime(2024, 3, 15, tzinfo=timezone.utc))

    def test_monthly_upcoming_due_respects_due_day_clamping(self):
        # Traditional monthly schedule on the 31st with no first_rent_due_date.
        settings = MockSettings(
            frequency_type='monthly',
            first_rent_due_date=None,
            due_day_of_month=31,
            bill_preview_enabled=True,
            bill_preview_days=5,
        )

        # Mar 5 should be in Feb coverage period, with upcoming due on Mar 31.
        ref = datetime(2026, 3, 5, tzinfo=timezone.utc)
        timeline = _calculate_rent_timeline(settings, ref)

        self.assertEqual(timeline['coverage_due_date'], datetime(2026, 2, 28, tzinfo=timezone.utc))
        self.assertEqual(timeline['upcoming_due_date'], datetime(2026, 3, 31, tzinfo=timezone.utc))
        self.assertEqual(timeline['preview_start_date'], datetime(2026, 3, 26, tzinfo=timezone.utc))

if __name__ == '__main__':
    unittest.main()
