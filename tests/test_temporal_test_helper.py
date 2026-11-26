"""tests/helpers/temporal.py answers exactly as the production resolver does."""

from datetime import date, datetime, timezone

from tests.helpers import temporal
from tests.helpers.classroom_initializer import initialize

NOON = datetime(2026, 10, 30, 19, 0, tzinfo=timezone.utc)


def test_system_time_helpers():
    with temporal.pinned_clock(NOON):
        assert temporal.now() == NOON
    assert temporal.shifted(NOON, minutes=-90) == datetime(2026, 10, 30, 17, 30, tzinfo=timezone.utc)
    assert temporal.calendar_days_later(NOON, 3) == datetime(2026, 11, 2, 19, 0, tzinfo=timezone.utc)
    assert temporal.seconds_between(NOON, temporal.shifted(NOON, hours=2)) == 7200


def test_class_time_helpers_follow_the_class_calendar_across_dst(app):
    with app.app_context():
        class_id = initialize("chemistry_p1", app).class_id  # America/Los_Angeles
        nine = temporal.class_wall_time(class_id, date(2026, 11, 1), 9)
        assert nine == datetime(2026, 11, 1, 17, 0, tzinfo=timezone.utc)  # 09:00 PST
        assert temporal.class_date_of(datetime(2026, 11, 2, 7, 30, tzinfo=timezone.utc), class_id) == date(2026, 11, 1)
        start, end = temporal.class_day_bounds(class_id, date(2026, 11, 1))
        assert temporal.seconds_between(start, end) == 25 * 3600
        # 12:00 PDT on Oct 31 + 1 day keeps 12:00 local, 25 elapsed hours later.
        assert temporal.calendar_days_later(datetime(2026, 10, 31, 19, 0, tzinfo=timezone.utc), 1, class_id=class_id) == \
            datetime(2026, 11, 1, 20, 0, tzinfo=timezone.utc)
