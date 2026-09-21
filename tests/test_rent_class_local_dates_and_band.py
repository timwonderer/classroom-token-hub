"""Rent's due date resolves in the class timezone, and its pricing band exists
before rent is priced (findings 25 and 24).

Both were found in the browser on the first rent configuration a teacher ever
performs, and neither is visible from a test that uses the server's own
timezone: the class timezone is forced here to one matching neither UTC nor a
developer's host, which is what makes the assertions meaningful.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import RentSettings
from app.services.class_configuration_query_service import get_rent_settings
from tests.helpers.class_domain import (
    enable_class_feature,
    update_expected_weekly_hours,
)
from tests.helpers.classroom_initializer import initialize_as_teacher


# Class timezone is immutable once set, so the zone is chosen at provisioning
# time via these fixtures rather than assigned afterwards.
CLASSROOM_FOR_TZ = {
    "America/Los_Angeles": "tz_pacific_p1",
    "Asia/Tokyo": "tz_tokyo_p1",
    "Pacific/Kiritimati": "tz_line_islands_p1",
}


def _prepare_rent_class(client, app, tz_name: str):
    """A logged-in teacher whose class is in ``tz_name``, with rent and CWI ready."""
    classroom = initialize_as_teacher(CLASSROOM_FOR_TZ[tz_name], client, app)
    with app.app_context():
        enable_class_feature(class_id=classroom.class_id, feature="rent")
    # CWI needs expected weekly hours; without them `calculate_cwi` returns None
    # and every pricing recommendation is correctly withheld.
    update_expected_weekly_hours(client, expected_weekly_hours=10)
    return classroom


def _post_rent(client, **overrides):
    form = {
        "rent_amount": "50.00",
        "frequency_type": "monthly",
        "due_day_of_month": "20",
        "first_rent_due_date": "2026-10-20",
        "grace_period_days": "3",
        "late_penalty_amount": "0.00",
        "late_penalty_type": "once",
        "bill_preview_days": "7",
    }
    form.update(overrides)
    return client.post("/admin/rent-settings", data=form, follow_redirects=False)


# --------------------------------------------------------------------------
# 25 — the due date the teacher typed is the due date that is stored
# --------------------------------------------------------------------------

# DO NOT reduce this to the Pacific case alone.
#
# The test database session runs in America/Los_Angeles; production runs in
# Etc/UTC. A naive datetime is therefore resolved against a DIFFERENT zone in the
# two environments, so for a Pacific class the shipped naive parse produced the
# correct instant here and the wrong one in production — the Pacific row below
# passes with or without the fix and proves nothing on this machine.
#
# Asia/Tokyo is the load-bearing case: no host or session timezone makes a naive
# parse land on Japanese local midnight, so it fails wherever the defect exists.
# This is the same trap the payroll first-pay-date fix documented, and it is why
# three instances of one defect reached production.
@pytest.mark.parametrize(
    "tz_name,expected_utc",
    [
        # Oct 20 00:00 PDT = 07:00 UTC. Environment-dependent; see above.
        ("America/Los_Angeles", datetime(2026, 10, 20, 7, 0, tzinfo=timezone.utc)),
        # Oct 20 00:00 JST = Oct 19 15:00 UTC. Independent of the host.
        ("Asia/Tokyo", datetime(2026, 10, 19, 15, 0, tzinfo=timezone.utc)),
        # UTC+14, the earliest civil time on Earth: Oct 20 00:00 there is Oct 19
        # 10:00 UTC, and Oct 18 in a UTC-12 session. Nothing about any host's
        # clock can make a naive parse produce this instant.
        ("Pacific/Kiritimati", datetime(2026, 10, 19, 10, 0, tzinfo=timezone.utc)),
    ],
)
def test_first_rent_due_date_is_stored_as_class_local_midnight(app, client, tz_name, expected_utc):
    classroom = _prepare_rent_class(client, app, tz_name)

    response = _post_rent(client)
    assert response.status_code == 302, response.data

    with app.app_context():
        settings = get_rent_settings(classroom.class_id)
        assert settings.first_rent_due_date == expected_utc, (
            f"{tz_name}: stored {settings.first_rent_due_date}, "
            f"expected class-local midnight {expected_utc}"
        )


@pytest.mark.parametrize(
    "tz_name", ["America/Los_Angeles", "Asia/Tokyo", "Pacific/Kiritimati"]
)
def test_the_page_shows_back_the_date_the_teacher_typed(app, client, tz_name):
    """Teacher and student must not be told different days for one obligation.

    The live symptom was exactly this disagreement: the teacher page formatted
    the stored instant in UTC and printed October 20, while the student page
    derived from ``cycle_boundary_at`` in class-local time and printed the 19th.
    """
    _prepare_rent_class(client, app, tz_name)

    _post_rent(client)
    page = client.get("/admin/rent-settings").data.decode()

    assert "October 20, 2026" in page, f"{tz_name}: the typed date is not shown back"
    assert "October 19, 2026" not in page, f"{tz_name}: the date moved a day"
    # The ISO value repopulates the date input, so a drifting read would walk the
    # date backwards one day on every open-and-resave.
    assert 'value="2026-10-20"' in page


def test_reopening_and_resaving_does_not_move_the_date(app, client):
    """Round-trip stability: the form's own value must survive a resubmit."""
    classroom = _prepare_rent_class(client, app, "Asia/Tokyo")

    _post_rent(client)
    with app.app_context():
        first = get_rent_settings(classroom.class_id).first_rent_due_date

    # Re-save exactly what the page would repopulate.
    _post_rent(client)
    with app.app_context():
        second = get_rent_settings(classroom.class_id).first_rent_due_date

    assert first == second, f"the due date drifted on resave: {first} -> {second}"


# --------------------------------------------------------------------------
# 24 — the pricing recommendation exists before rent is priced
# --------------------------------------------------------------------------

def test_rent_band_renders_before_any_rent_policy_exists(app, client):
    """The band is gated on payroll, not on the decision it exists to inform.

    Against the shipped code the server emitted no ``data-canonical-*`` on a
    class with no RentSettings row, and the async fallback could not rescue it,
    so the page read "Recommendation unavailable — insufficient data" directly
    above a printout of the CWI, the policy and the percentage band.
    """
    classroom = _prepare_rent_class(client, app, "America/Los_Angeles")

    with app.app_context():
        # Remove every rent policy: this is a class that has never priced rent.
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"clear-rent:{classroom.class_id}"):
            RentSettings.query.filter_by(class_id=classroom.class_id).delete()
            db.session.flush()
        assert get_rent_settings(classroom.class_id) is None

    page = client.get("/admin/rent-settings").data.decode()

    assert "data-canonical-min" in page, (
        "no server-rendered pricing band on a class that has not priced rent yet"
    )
    assert "data-canonical-max" in page


def test_economy_validate_resolves_payroll_from_the_session(app, client):
    """The validator must not need the client to name the class it is already in.

    ``_resolve_admin_payroll_settings_for_class_id`` took the canonical context
    and read only the request-supplied ``class_id``, so the endpoint reported
    payroll unconfigured for a class that had payroll configured — the second of
    finding 24's two causes, and the one that stopped the client retry from
    rescuing the first.
    """
    _prepare_rent_class(client, app, "America/Los_Angeles")

    # Exactly what static/js/economy-balance.js sends: no class_id.
    response = client.post(
        "/admin/api/economy/validate/rent",
        json={"value": "50.00", "frequency": "monthly", "frequency_type": "monthly"},
    )

    assert response.status_code == 200, response.data
    payload = response.get_json()
    assert "Configure payroll first" not in (payload.get("message") or ""), (
        "the validator could not see payroll that is configured for this class"
    )
