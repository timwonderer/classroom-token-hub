"""A rent policy saved mid-cycle must be reported as pending, not as current.

``rent_settings`` is append-only (DOM-POL-001 §VI.1) and a bill cycle freezes the
``policy_uuid`` it was created under (§VII), so a teacher who changes rent while a
cycle is open does not change what anyone is billed this period: the new terms
bind when ``reconcile_rent`` mints the successor cycle at ``next_assessment_at``.

That deferral is the protection — a cycle already underway is never altered — but
the admin page rendered the newest ``IN_USE`` row under the heading "Current Rent
Configuration" and flashed a bare "updated successfully", so the pending policy
was presented as the one in force. These tests hold the correction: the page
names which policy students are actually on, and when the saved one starts.

Reference instants are injected, never read from a wall clock (SPEC-TIME-001),
and the effective date is asserted as a class-local date, not a UTC one
(SPEC-TIME-001 §CLE).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from app.feats.reconcile_rent_feat import execute_reconcile_rent
from app.models import BillCycle
from app.routes.admin import _resolve_rent_policy_deferral
from app.services.class_configuration_query_service import get_rent_settings
from tests.helpers.class_domain import customize_rent_settings, enable_class_feature
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher

# Class default tz is America/Los_Angeles, so a noon-UTC instant is still the
# same class-local calendar day.
_FIRST_DUE = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
_T_INITIAL = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
_T_AFTER_BOUNDARY = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)


def _setup_rent_class(class_id, rent_amount=Decimal("50.00")):
    enable_class_feature(class_id=class_id, feature="rent")
    return customize_rent_settings(
        class_id,
        frequency_type="monthly",
        due_day_of_month=1,
        first_rent_due_date=_FIRST_DUE,
        grace_period_days=3,
        rent_amount=rent_amount,
        late_penalty_amount=Decimal("0.00"),
    )


def test_no_deferral_before_any_cycle_exists(app):
    """The first save is in force immediately — nothing to warn about."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        settings = _setup_rent_class(classroom.class_id)

        assert BillCycle.query.filter_by(class_id=classroom.class_id).count() == 0
        assert _resolve_rent_policy_deferral(classroom.class_id, settings) is None


def test_no_deferral_when_the_open_cycle_already_carries_the_newest_policy(app):
    """A cycle minted under the current policy is not a divergence."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        _setup_rent_class(classroom.class_id)
        execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)

        current = get_rent_settings(classroom.class_id)
        assert _resolve_rent_policy_deferral(classroom.class_id, current) is None


def test_policy_saved_midcycle_is_reported_as_pending(app):
    """The saved policy is named pending, and the in-force terms are the old ones."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        _setup_rent_class(classroom.class_id, rent_amount=Decimal("50.00"))
        execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)
        enforced = get_rent_settings(classroom.class_id)

        pending = customize_rent_settings(
            classroom.class_id, rent_amount=Decimal("75.00")
        )
        assert pending.policy_uuid != enforced.policy_uuid

        deferral = _resolve_rent_policy_deferral(classroom.class_id, pending)

        assert deferral is not None
        assert deferral["cycle_number"] == 1
        assert deferral["is_terminal"] is False
        assert deferral["amount_changed"] is True
        # What students are billed now is the OLD amount, not the saved one.
        assert deferral["enforced"]["amount"] == "$50.00"
        assert deferral["enforced"]["cadence"] == "per month"
        assert deferral["pending"]["amount"] == "$75.00"
        # Class-local date of the successor boundary, which is when the pending
        # policy binds. A UTC reading of the same instant would land on Jan 31
        # for this class.
        assert deferral["takes_effect_on"] == date(2026, 2, 1)
        assert deferral["display_takes_effect_on"] == "February 01, 2026"


def test_deferral_clears_once_the_cycle_advances(app):
    """Advancing binds the pending policy, so the notice must stop appearing."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        _setup_rent_class(classroom.class_id, rent_amount=Decimal("50.00"))
        execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)

        pending = customize_rent_settings(
            classroom.class_id, rent_amount=Decimal("75.00")
        )
        assert _resolve_rent_policy_deferral(classroom.class_id, pending) is not None

        execute_reconcile_rent(
            classroom.class_id, reference_time_utc=_T_AFTER_BOUNDARY
        )

        current = get_rent_settings(classroom.class_id)
        assert current.policy_uuid == pending.policy_uuid
        assert _resolve_rent_policy_deferral(classroom.class_id, current) is None


def test_terminal_cycle_reports_that_the_saved_policy_never_binds(app):
    """A lineage with no successor cannot ever adopt the saved terms."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        from app.extensions import db
        from app.feats.base import FEATContext

        _setup_rent_class(classroom.class_id)
        execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)

        cycle = BillCycle.query.filter_by(
            internal_ref=f"rent:{classroom.class_id}"
        ).one()
        with FEATContext(
            "FEAT-TEST-SETUP", idempotency_key=f"terminal:{classroom.class_id}"
        ):
            cycle.next_assessment_at = None
            db.session.flush()

        pending = customize_rent_settings(
            classroom.class_id, rent_amount=Decimal("75.00")
        )
        deferral = _resolve_rent_policy_deferral(classroom.class_id, pending)

        assert deferral is not None
        assert deferral["is_terminal"] is True
        assert deferral["takes_effect_on"] is None
        assert deferral["display_takes_effect_on"] == ""


def test_rent_settings_page_names_the_policy_students_are_on(app, client):
    """The rendered page must carry the notice and stop calling pending 'current'."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        _setup_rent_class(classroom.class_id, rent_amount=Decimal("50.00"))
        execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)
        customize_rent_settings(classroom.class_id, rent_amount=Decimal("75.00"))

    response = client.get("/admin/rent-settings")
    assert response.status_code == 200
    body = response.data.decode()

    assert "These rent terms start February 01, 2026" in body
    # The in-force amount is stated, not just the saved one.
    assert "$50.00" in body
    # The heading no longer asserts the pending policy is the current one.
    assert "Current Rent Configuration" not in body
    assert "Saved Rent Configuration" in body


def test_rent_settings_page_says_current_when_nothing_is_deferred(app, client):
    """Mutation proof: with no divergence the notice and relabel must be absent."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        _setup_rent_class(classroom.class_id, rent_amount=Decimal("50.00"))
        execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)

    response = client.get("/admin/rent-settings")
    assert response.status_code == 200
    body = response.data.decode()

    assert "These rent terms start" not in body
    assert "Current Rent Configuration" in body
    assert "Saved Rent Configuration" not in body
