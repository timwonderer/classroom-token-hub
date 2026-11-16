"""FEAT-STOR-007 §V.A — superseded and withdrawn insurance versions (owner ruling 2026-10-14).

DOM-STORE-001 §VIII.E.1 *Continuation after a policy edit* / *Withdrawn offering*:

- an edit supersedes the holder's version: the holder's entitlement keeps its
  version, stops renewing and ends at its boundary; a NEW entitlement under the
  latest successor on sale begins there, its lineage anchored at the boundary,
  its first premium assessed and auto-paid at the assessment point, with no
  waiting period;
- a version hidden or retired with no successor on sale stops renewing: coverage
  ends at the boundary and nothing new is granted;
- a student who stops renewal before the assessment point is not continued.

Reuses the controlled-clock harness of test_insurance_coverage_renewal_feat.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from app.extensions import db
from app.feats.class_configuration import (
    configure_insurance_definition,
    set_insurance_definition_availability,
)
from app.feats.insurance_coverage_renewal_feat import premium_correlation_id
from app.models import BillCycle, EntitlementEvent
from app.services import insurance_definition_service as defs
from app.services import obligations_service
from app.services.insurance_coverage_service import is_insurance_usable, premium_lineage_ref
from tests.test_insurance_coverage_renewal_feat import (  # noqa: F401  (world fixture)
    B1, PREMIUM, PREVIEW_2, PURCHASE, US,
    _cancel, _clock, _expiry_job, local, world,
)


def _edit(w, **changes):
    """Teacher edits the current policy: a new version superseding it."""
    submission = dict(
        insurance_type="TRANSACTION", premium=str(PREMIUM), charge_frequency="WEEKLY",
        reimbursement_percentage="100", payout_multiple="5",
        claims_per_week_equivalent="1", claim_window_days="7",
        bill_preview_days=3, nonpayment_mode="ACCUMULATE", title="Cover v2",
    )
    submission.update(changes)
    row = configure_insurance_definition(
        class_id=w.class_id, submission=submission, canonical_context=w.teacher_ctx,
        supersedes_policy_uuid=w.policy_uuid,
        correlation_id=f"corr_{uuid4().hex}",
        idempotency_key=f"FEAT-CLASS-003:edit:{uuid4().hex}",
    )
    db.session.commit()
    return row.policy_uuid


def _set_state(w, policy_uuid, state):
    set_insurance_definition_availability(
        class_id=w.class_id, policy_uuid=policy_uuid, availability_state=state,
        canonical_context=w.teacher_ctx,
        correlation_id=f"corr_{uuid4().hex}", idempotency_key=f"avail:{uuid4().hex}",
    )
    db.session.commit()


def _grants(w):
    return (
        EntitlementEvent.query.filter_by(
            class_id=w.class_id, target_seat_id=w.seat_id,
            entitlement_type="INSURANCE", event_type="GRANTED",
        ).order_by(EntitlementEvent.timestamp.asc()).all()
    )


def _cycles(entitlement_id, class_id):
    return (
        BillCycle.query.filter_by(class_id=class_id, internal_ref=premium_lineage_ref(entitlement_id))
        .order_by(BillCycle.cycle_number.asc()).all()
    )


def test_edit_continues_coverage_under_the_successor_at_the_boundary(world):
    w = world()
    w.fund(PURCHASE - timedelta(hours=1), Decimal("40.00"))
    w.buy()
    successor = _edit(w, premium="15.00")

    result = w.renew(PREVIEW_2)
    assert result.renewal_stopped_at == B1
    assert result.cycles_scheduled == []  # the old version is not renewed

    old_grant, new_grant = _grants(w)
    assert old_grant.entitlement_id == w.entitlement_id
    assert old_grant.payload["policy_uuid"] == w.policy_uuid  # never rewritten
    assert new_grant.payload["policy_uuid"] == successor
    assert new_grant.payload["continues_entitlement_id"] == w.entitlement_id
    assert new_grant.timestamp == B1

    # The new lineage starts at the boundary, anchored there, under the successor.
    [cycle] = _cycles(new_grant.entitlement_id, w.class_id)
    assert (cycle.cycle_number, cycle.cycle_boundary_at, cycle.policy_uuid) == (1, B1, successor)
    assert cycle.next_assessment_at == local(1, 24)

    # Its first premium is the successor's price, due at the boundary, auto-paid now.
    premium = obligations_service.get_obligation_state(premium_correlation_id(new_grant.entitlement_id, 1))
    assert premium.due_at == B1 and premium.is_satisfied
    assert premium.assessed_amount == Decimal("15.00")

    # The old coverage runs to the boundary; the new one takes over there.
    _expiry_job(B1 + timedelta(hours=4))
    for t in (B1 - timedelta(days=2), B1 - US):
        assert is_insurance_usable(w.class_id, w.entitlement_id, reference_time_utc=t)
        assert not is_insurance_usable(w.class_id, new_grant.entitlement_id, reference_time_utc=t)
    for t in (B1, B1 + timedelta(days=3)):
        assert not is_insurance_usable(w.class_id, w.entitlement_id, reference_time_utc=t)
        assert is_insurance_usable(w.class_id, new_grant.entitlement_id, reference_time_utc=t)


def test_continuation_is_idempotent(world):
    w = world()
    w.fund(PURCHASE - timedelta(hours=1), Decimal("40.00"))
    w.buy()
    _edit(w)
    w.renew(PREVIEW_2)
    again = w.renew(PREVIEW_2 + timedelta(hours=2))
    assert not again.wrote_anything
    assert len(_grants(w)) == 2


def test_continuation_has_no_waiting_period(world):
    w = world()
    w.fund(PURCHASE - timedelta(hours=1), Decimal("40.00"))
    w.buy()
    _edit(w, waiting_period_days="7")
    w.renew(PREVIEW_2)
    _expiry_job(B1 + timedelta(hours=1))

    w.entitlement_id = _grants(w)[1].entitlement_id
    txn = w.loss(B1 + timedelta(days=1))
    filed = w.file_claim(B1 + timedelta(days=1, hours=1), txn)
    assert filed.success, filed.error_message  # not WAITING_PERIOD_NOT_ELAPSED


def test_cadence_change_anchors_the_new_lineage_at_the_boundary(world):
    w = world()
    w.fund(PURCHASE - timedelta(hours=1), Decimal("100.00"))
    w.buy()
    _edit(w, charge_frequency="MONTHLY", bill_preview_days=5)
    w.renew(PREVIEW_2)
    [cycle] = _cycles(_grants(w)[1].entitlement_id, w.class_id)
    assert (cycle.cycle_boundary_at, cycle.next_assessment_at) == (B1, local(2, 17))


def test_edits_in_a_row_continue_onto_the_latest_version(world):
    w = world()
    w.fund(PURCHASE - timedelta(hours=1), Decimal("40.00"))
    w.buy()
    first = _edit(w, premium="12.00")
    w.policy_uuid = first
    latest = _edit(w, premium="14.00")
    w.renew(PREVIEW_2)
    assert _grants(w)[1].payload["policy_uuid"] == latest


def test_hidden_version_without_successor_stops_renewing(world):
    w = world()
    w.fund(PURCHASE - timedelta(hours=1), Decimal("40.00"))
    w.buy()
    _set_state(w, w.policy_uuid, defs.HIDDEN)

    result = w.renew(PREVIEW_2)
    assert result.renewal_stopped_at == B1
    assert len(_grants(w)) == 1  # nothing new granted
    _expiry_job(B1 + timedelta(hours=4))
    [expired] = w.expired_events()
    assert expired.timestamp == B1
    assert w.usable(B1 - US) and not w.usable(B1)


def test_retired_version_without_successor_stops_renewing(world):
    w = world()
    w.fund(PURCHASE - timedelta(hours=1), Decimal("40.00"))
    w.buy()
    _set_state(w, w.policy_uuid, defs.RETIRED)
    assert w.renew(PREVIEW_2).renewal_stopped_at == B1
    assert len(_grants(w)) == 1


def test_successor_withdrawn_before_the_boundary_ends_coverage(world):
    w = world()
    w.fund(PURCHASE - timedelta(hours=1), Decimal("40.00"))
    w.buy()
    successor = _edit(w)
    _set_state(w, successor, defs.HIDDEN)
    assert w.renew(PREVIEW_2).renewal_stopped_at == B1
    assert len(_grants(w)) == 1


def test_reactivated_offering_continues_its_holders(world):
    w = world()
    w.fund(PURCHASE - timedelta(hours=1), Decimal("40.00"))
    w.buy()
    _set_state(w, w.policy_uuid, defs.HIDDEN)
    # Putting it back on sale mints an identical successor (admin reactivate route).
    reactivated = _edit(w, title="Cover")
    w.renew(PREVIEW_2)
    assert _grants(w)[1].payload["policy_uuid"] == reactivated


def test_student_who_stops_renewal_first_is_not_continued(world):
    w = world()
    w.fund(PURCHASE - timedelta(hours=1), Decimal("40.00"))
    w.buy()
    _cancel(w, local(1, 12))
    _edit(w)
    assert not w.renew(PREVIEW_2).wrote_anything
    assert len(_grants(w)) == 1


def test_grouped_tier_edit_continues_despite_the_group_exclusion(world):
    w = world(tier_group="Cover Plans", tier_level=1)
    w.fund(PURCHASE - timedelta(hours=1), Decimal("40.00"))
    w.buy()
    successor = _edit(w, tier_group_id=defs.get_insurance_definition(w.policy_uuid, class_id=w.class_id).tier_group_id, tier_level=1, premium="11.00")
    w.renew(PREVIEW_2)
    assert _grants(w)[1].payload["policy_uuid"] == successor


def test_unpaid_first_premium_gates_the_continuation(world):
    w = world()
    w.fund(PURCHASE - timedelta(hours=1))  # exactly the first premium
    w.buy()
    _edit(w)
    w.renew(PREVIEW_2)
    new_id = _grants(w)[1].entitlement_id
    assert obligations_service.get_obligation_state(premium_correlation_id(new_id, 1)).is_outstanding
    with _clock(B1 + timedelta(hours=1)):
        assert not is_insurance_usable(w.class_id, new_id, reference_time_utc=B1 + timedelta(hours=1))


# --------------------------------------------------------------------------- #
# What the student sees on My coverage (SPEC-ECON-003 §4.4.2)                   #
# --------------------------------------------------------------------------- #


def _my_coverage(client, at):
    with _clock(at):
        return client.get("/student/insurance").get_data(as_text=True)


def _logged_in(world, client):
    from tests.helpers.canonical_classroom import login_student

    w = world()
    w.fund(PURCHASE - timedelta(hours=1), Decimal("40.00"))
    w.buy()
    login_student(client, w.student)
    return w


def test_student_sees_the_change_before_it_is_billed(world, client):
    w = _logged_in(world, client)
    _edit(w, premium="15.00", title="Cover Plus")
    html = _my_coverage(client, local(1, 12))
    assert "Your teacher changed this plan" in html
    assert "Cover Plus" in html and "$15.00" in html
    assert "January 14" in html  # first premium charged at the assessment point
    assert "cancel this coverage before then" in html


def test_after_the_move_the_old_card_says_moving_not_cancelled(world, client):
    w = _logged_in(world, client)
    _edit(w, title="Cover Plus")
    w.renew(PREVIEW_2)
    html = _my_coverage(client, local(1, 15))
    assert "Moving to Cover Plus" in html
    assert "You cancelled this coverage" not in html
    assert "Starts Jan 17" in html  # the continuing coverage's own card


def test_withdrawn_plan_says_ending(world, client):
    w = _logged_in(world, client)
    _set_state(w, w.policy_uuid, defs.HIDDEN)
    assert "This plan is ending" in _my_coverage(client, local(1, 12))
    w.renew(PREVIEW_2)
    html = _my_coverage(client, local(1, 15))
    assert "This plan is ending" in html
    assert "You cancelled this coverage" not in html


def test_student_cancel_after_an_edit_still_reads_as_cancelled(world, client):
    w = _logged_in(world, client)
    _edit(w, title="Cover Plus")
    _cancel(w, local(1, 12))
    html = _my_coverage(client, local(1, 12, 12))
    assert "You cancelled this coverage" in html
    assert "This plan is ending" not in html
