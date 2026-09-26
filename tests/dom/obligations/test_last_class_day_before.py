"""obligations_service.last_class_day_before — SPEC-TIME-001 §XII, INV-ARC-015 §VII.

The last day of a half-open period [start, end) is the class-local day holding
its last instant. It is derived through resolver primitives, not by subtracting
a calendar day outside the resolver.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.services.obligations_service import last_class_day_before
from app.utils.canonical_temporal_resolver import CLASS_LEVEL_EVALUATION, canonical_temporal_resolver
from tests.helpers.classroom_initializer import initialize


def _local_start(class_id, day):
    return canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=SimpleNamespace(class_id=class_id),
        primitive="evaluation_day_boundaries",
        evaluation_date=day,
    ).boundary_start_utc


def _shift(class_id, instant, seconds):
    return canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=SimpleNamespace(class_id=class_id),
        primitive="shift_timestamp",
        timestamp=instant,
        elapsed_seconds=seconds,
    ).shifted_timestamp_utc


def test_period_ending_at_class_midnight_ends_on_the_day_before(app):
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        end = _local_start(classroom.class_id, date(2026, 10, 25))
        assert last_class_day_before(classroom.class_id, end) == date(2026, 10, 24)


def test_period_ending_mid_day_ends_on_that_same_day(app):
    """Distinguishes the rule from "the end's class date, minus one day"."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        end = _shift(classroom.class_id, _local_start(classroom.class_id, date(2026, 10, 25)), 15 * 3600)
        assert last_class_day_before(classroom.class_id, end) == date(2026, 10, 25)


def test_period_ending_at_midnight_across_the_dst_change_ends_the_day_before(app):
    """Nov 1 2026 is the US fall-back; class-local midnight on Nov 2 is still Nov 1's end."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        end = _local_start(classroom.class_id, date(2026, 11, 2))
        assert last_class_day_before(classroom.class_id, end) == date(2026, 11, 1)
