"""A change saved for the next cycle is an effective-dated row, not a transition.

Operator ruling 2026-09-30 (DOM-CLASS-003 §VII): each domain's own append-only
table is its policy history, and a change saved mid-cycle is an appended row
effective at that domain's next boundary. Nothing is queued and nothing is
activated later; the row is in force from its date, and visible as pending until
then (§X).

* Rent: a scheduled rebalance appends one ``rent_settings`` row dated to the first
  rent period not yet issued. The open period keeps the policy it froze; the next
  period is billed on the new terms.
* A seat claimed mid-period is billed on that period's own terms, not on a policy
  saved since (the roster backfill used the newest row, so a mid-period save
  re-priced the open period for anyone who joined after it).
* Economic Engine: a version dated for later is pending until its date. The
  engine was resolved by ``created_at``, so a future-dated version governed from
  the moment it was saved.

Rent instants are injected in the year 2999 so the open period is genuinely in
the future of the wall clock the route reads (SPEC-TIME-001).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.class_configuration.feat_class_005_economic_engine_evolution import (
    execute_evolve_economic_engine,
)
from app.feats.reconcile_rent_feat import execute_reconcile_rent
from app.models import BillCycle, ClassFeature, ObligationAssessment, RentSettings, Seat
from app.services.class_configuration_query_service import (
    economic_engine_effective_at,
    get_current_economic_engine,
    get_rent_settings,
    is_feature_enabled,
)
from app.services.context_resolver import CanonicalContext
from app.utils.canonical_temporal_resolver import utc_now
from app.utils.economy_rebalance import get_pending_rebalance_effective_at
from tests.helpers.class_domain import (
    customize_rent_settings,
    enable_class_feature,
    update_expected_weekly_hours,
)
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher

_FIRST_DUE = datetime(2999, 1, 1, 12, 0, tzinfo=timezone.utc)
_MID_PERIOD = datetime(2999, 1, 15, 12, 0, tzinfo=timezone.utc)


def _rent_class(class_id, *, rent_amount):
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


def _cycles(class_id):
    return (
        BillCycle.query.filter_by(internal_ref=f"rent:{class_id}")
        .order_by(BillCycle.cycle_number.asc())
        .all()
    )


def _assessed_policy(class_id, seat_id, cycle):
    return ObligationAssessment.query.filter_by(
        class_id=class_id, seat_id=seat_id, obligation_type="RENT",
        event_type="ASSESSMENT", bill_cycle_id=cycle.id,
    ).one().policy_uuid


def _teacher_context(classroom):
    return CanonicalContext(
        user_id=classroom.teacher_user.id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
        actor_role="teacher",
    )


def test_a_rebalance_saved_mid_cycle_takes_effect_at_the_boundary(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    cid = classroom.class_id
    update_expected_weekly_hours(client, "40")
    with app.app_context():
        old_uuid = _rent_class(cid, rent_amount=Decimal("1.00")).policy_uuid
        execute_reconcile_rent(cid, reference_time_utc=_FIRST_DUE)
        (open_cycle,) = _cycles(cid)
        assert open_cycle.policy_uuid == old_uuid
        boundary = open_cycle.next_assessment_at
        db.session.commit()

    body = client.get("/admin/economic-engine?review_rebalance=1").get_data(as_text=True)
    offered = set(re.findall(r'name="selected_changes"[^>]*value="([^"]+)"', body))
    assert "rent" in offered, offered

    response = client.post(
        "/admin/economy-policy/rebalance",
        data={"selected_changes": ["rent"]},
    )
    assert response.status_code == 302, response.get_data(as_text=True)[:2000]

    with app.app_context():
        # One appended rent row, dated to the boundary that closes the open period.
        new = get_rent_settings(cid)
        assert new.policy_uuid != old_uuid
        assert new.rent_amount > Decimal("1.00")
        assert new.rent_effective_at == boundary
        assert RentSettings.query.filter_by(class_id=cid).count() == 3
        # Visible as pending until then (DOM-CLASS-003 §X).
        assert get_pending_rebalance_effective_at(cid) == boundary
        # The open period keeps the terms it froze.
        seat_id = classroom.students[0].seat.id
        (open_cycle,) = _cycles(cid)
        assert _assessed_policy(cid, seat_id, open_cycle) == old_uuid

        # Past the boundary the next period is billed on the new terms.
        execute_reconcile_rent(cid, reference_time_utc=boundary + timedelta(hours=1))
        first, second = _cycles(cid)
        assert first.policy_uuid == old_uuid
        assert second.policy_uuid == new.policy_uuid
        assert _assessed_policy(cid, seat_id, second) == new.policy_uuid
        assert _assessed_policy(cid, seat_id, first) == old_uuid

    page = client.get("/admin/economic-engine").get_data(as_text=True)
    assert "Economy Update Scheduled" in page


def _schedule_rent_rebalance(client, app, *, extra_form=None):
    """A class with an open rent period and a rent rebalance saved in it.

    Returns (class_id, old policy_uuid, boundary)."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    cid = classroom.class_id
    update_expected_weekly_hours(client, "40")
    with app.app_context():
        old_uuid = _rent_class(cid, rent_amount=Decimal("1.00")).policy_uuid
        execute_reconcile_rent(cid, reference_time_utc=_FIRST_DUE)
        (open_cycle,) = _cycles(cid)
        boundary = open_cycle.next_assessment_at
        db.session.commit()
    response = client.post(
        "/admin/economy-policy/rebalance",
        data={"selected_changes": ["rent"], **(extra_form or {})},
    )
    assert response.status_code == 302, response.get_data(as_text=True)[:2000]
    return cid, old_uuid, boundary


def test_a_stale_apply_immediately_post_still_dates_rent_to_the_next_unbilled_period(client, app):
    """Owner ruling 2026-09-30: rent has one choice. A form that still posts
    ``activation_mode=immediate`` gets the same dated row, not an immediate one."""
    cid, old_uuid, boundary = _schedule_rent_rebalance(
        client, app, extra_form={"activation_mode": "immediate", "confirm_immediate": "yes"},
    )
    with app.app_context():
        new = get_rent_settings(cid)
        assert new.policy_uuid != old_uuid
        assert new.rent_effective_at == boundary


def test_a_policy_mode_change_leaves_a_scheduled_rebalance_in_force(client, app):
    """Owner ruling 2026-09-30: scheduling the rebalance was an explicit teacher
    action; changing mode must not implicitly revoke it (DOM-CLASS-003 §IX,
    FEAT-ECON-001 §X)."""
    cid, old_uuid, boundary = _schedule_rent_rebalance(client, app)
    with app.app_context():
        scheduled = get_rent_settings(cid)
        scheduled_uuid, rows_before = scheduled.policy_uuid, RentSettings.query.filter_by(class_id=cid).count()
        assert get_pending_rebalance_effective_at(cid) == boundary

    response = client.post("/admin/economy-policy", data={"policy_mode": "tight"})
    assert response.status_code == 302, response.get_data(as_text=True)[:2000]

    with app.app_context():
        assert get_current_economic_engine(cid).economy_policy_mode == "tight"
        # The scheduled row is untouched and still the next period's terms.
        assert RentSettings.query.filter_by(class_id=cid).count() == rows_before
        assert get_rent_settings(cid).policy_uuid == scheduled_uuid
        assert get_pending_rebalance_effective_at(cid) == boundary
        execute_reconcile_rent(cid, reference_time_utc=boundary + timedelta(hours=1))
        first, second = _cycles(cid)
        assert first.policy_uuid == old_uuid
        assert second.policy_uuid == scheduled_uuid


def test_a_seat_claimed_mid_period_is_billed_on_that_periods_terms(app):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    with app.app_context():
        old = _rent_class(cid, rent_amount=Decimal("50.00"))
        late_seat_id = classroom.students[0].seat.id
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"unclaim:{late_seat_id}"):
            Seat.query.filter_by(id=late_seat_id).update({"claimed_at": None})
            db.session.flush()
        execute_reconcile_rent(cid, reference_time_utc=_FIRST_DUE)
        (open_cycle,) = _cycles(cid)

        # The teacher saves new rent terms while the period is open...
        new = customize_rent_settings(cid, rent_amount=Decimal("75.00"))
        assert new.policy_uuid != old.policy_uuid

        # ...and then a student claims their seat.
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"claim:{late_seat_id}"):
            Seat.query.filter_by(id=late_seat_id).update({"claimed_at": _MID_PERIOD})
            db.session.flush()
        execute_reconcile_rent(cid, reference_time_utc=_MID_PERIOD)

        assert _assessed_policy(cid, late_seat_id, open_cycle) == old.policy_uuid


def test_an_engine_version_dated_for_later_is_pending_until_its_date(app):
    classroom = initialize("chemistry_p1", app)
    cid = classroom.class_id
    with app.app_context():
        before = get_current_economic_engine(cid)
        effective_at = utc_now() + timedelta(days=7)
        result = execute_evolve_economic_engine(
            canonical_context=_teacher_context(classroom),
            class_id=cid,
            updates={"flat_overdraft_fee": 3.0},
            feature_list=[
                feature for feature in ClassFeature.feature_names()
                if is_feature_enabled(cid, feature)
            ],
            effective_at=effective_at.isoformat(),
            idempotency_key=f"engine-dated:{cid}",
        )
        assert result.success, result.error_message

        # Still the version in force now; the new one governs from its date.
        assert get_current_economic_engine(cid).economic_version_id == before.economic_version_id
        dated = economic_engine_effective_at(cid, effective_at)
        assert dated.economic_version_id == result.new_engine_id
        assert Decimal(str(dated.flat_overdraft_fee)) == Decimal("3.00")
        assert get_pending_rebalance_effective_at(cid) == effective_at
