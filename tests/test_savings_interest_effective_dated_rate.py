"""A savings rate dated for later never accrues before its effective date.

SPEC-ECON-001 §9.2 (1.3): each class-local day accrues at the rate in force at
the end of that day — the Economic Engine version with the greatest
``effective_at`` at or before that instant (DOM-CLASS-003 §VII). The accrual
timeline ordered versions by ``created_at``, so a teacher who saved a new rate
on Monday, dated to take effect on Thursday, had it paid from Monday: the
scheduled job and the student's forecast both credited the new rate for days
it did not govern.

Driven through the real scheduled job (``run_savings_interest_job``) and the
forecast the student dashboard shows (``forecast_savings``), with the resolver
clock pinned (SPEC-TIME-001 §11).
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from app.feats.class_configuration.feat_class_005_economic_engine_evolution import (
    execute_evolve_economic_engine,
)
from app.models import ClassFeature
from app.services.class_configuration_query_service import is_feature_enabled
from app.services.context_resolver import CanonicalContext
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.test_savings_interest_payout_cadence import (
    RATE,
    _cents,
    _configure_interest,
    _forecast,
    _fund_savings,
    _interest_rows,
    _local,
    _next_monday,
    _pinned_clock,
    _tick,
)

NEW_RATE = RATE * 2


def _save_rate_dated_for_later(monkeypatch, app, classroom, *, saved_at, effective_at):
    context = CanonicalContext(
        user_id=classroom.teacher_user.id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
        actor_role="teacher",
    )
    with app.app_context(), _pinned_clock(monkeypatch, saved_at):
        result = execute_evolve_economic_engine(
            canonical_context=context,
            class_id=classroom.class_id,
            updates={"interest_rate": float(NEW_RATE)},
            feature_list=[
                feature for feature in ClassFeature.feature_names()
                if is_feature_enabled(classroom.class_id, feature)
            ],
            effective_at=effective_at.isoformat(),
            idempotency_key=f"dated-rate:{classroom.class_id}",
        )
        assert result.success, result.error_message


def _class_with_rate_dated_for_later(client, app, monkeypatch):
    """1000.00 in savings from Monday; a doubled rate saved Monday 02:00, in
    force from Thursday noon. A day accrues at the rate in force at its end, so
    Mon-Wed earn the old rate and Thu-Sun the new one."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    tz_name = classroom.economy.class_timezone
    seat = classroom.students[0].seat
    _configure_interest(client, classroom, payout="weekly", calc="simple")

    monday = _next_monday(tz_name)
    _fund_savings(monkeypatch, app, classroom, seat, "1000.00", _local(tz_name, monday, 0, 30))
    _tick(monkeypatch, app, _local(tz_name, monday, 1))  # settles the deposit
    _save_rate_dated_for_later(
        monkeypatch, app, classroom,
        saved_at=_local(tz_name, monday, 2),
        effective_at=_local(tz_name, monday + timedelta(days=3), 12),
    )
    expected = _cents(
        Decimal("1000.00") * RATE / Decimal("365") * 3
        + Decimal("1000.00") * NEW_RATE / Decimal("365") * 4
    )
    return classroom, seat, tz_name, monday, expected


def test_the_payout_job_accrues_a_dated_rate_only_from_its_effective_date(client, app, monkeypatch):
    classroom, seat, tz_name, monday, expected = _class_with_rate_dated_for_later(client, app, monkeypatch)

    _tick(monkeypatch, app, _local(tz_name, monday + timedelta(days=7), 1))

    assert [row.amount for row in _interest_rows(app, classroom, seat)] == [expected]


def test_the_forecast_projects_a_dated_rate_only_from_its_effective_date(client, app, monkeypatch):
    classroom, seat, tz_name, monday, expected = _class_with_rate_dated_for_later(client, app, monkeypatch)

    forecast = _forecast(monkeypatch, app, classroom, seat, _local(tz_name, monday, 3), months=1)

    assert forecast.next_credit == expected
    # ...and the job then credits exactly what was forecast (SPEC-ECON-001 §10).
    _tick(monkeypatch, app, _local(tz_name, monday + timedelta(days=7), 1))
    assert [row.amount for row in _interest_rows(app, classroom, seat)] == [forecast.next_credit]
