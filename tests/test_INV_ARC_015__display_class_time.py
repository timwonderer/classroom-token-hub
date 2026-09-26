"""Classroom pages display class time — INV-ARC-015 §X.2.

``strftime`` on a stored UTC instant renders the UTC date, which is a different
day from the class's for part of every day. Dates a teacher picks are stored as
the exclusive end of the chosen class day, so the date to show is the last day
before that instant, never the instant's own date.

Dates are in 2030 so that nothing here expires against the real clock.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import app.utils.canonical_temporal_resolver as resolver_module
from app.extensions import db
from app.feats.base import FEATContext
from app.feats.class_configuration import configure_insurance_definition
from app.feats.purchase_insurance_feat import execute_purchase_insurance
from app.models import Announcement
from app.routes.admin import _end_of_day_utc
from app.services.announcement_service import create_class_announcement
from app.services.context_resolver import CanonicalContext
from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION,
    SYSTEM_LEVEL_EVALUATION,
    canonical_temporal_resolver,
    utc_now,
)
from app.utils.transaction_idempotency import create_idempotent_transaction
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_student, initialize_as_teacher
from tests.helpers.store_products import publish_store_product


def _utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


@contextmanager
def _pinned_clock(monkeypatch, instant):
    """Pins the resolver's clock — the one application code reads."""

    class _Pinned(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    with monkeypatch.context() as patch:
        patch.setattr(resolver_module, "datetime", _Pinned)
        yield


# The end of Oct 10 in Los Angeles (00:00 PDT Oct 11) is 07:00 UTC on Oct 11.
CHOSEN_DAY = date(2030, 10, 10)
END_OF_CHOSEN_DAY_PACIFIC = _utc(2030, 10, 11, 7, 0)


# --------------------------------------------------------------------------- #
# Announcements                                                                #
# --------------------------------------------------------------------------- #

def test_INV_ARC_015__announcement_expires_at_the_end_of_the_chosen_class_day(client, app):
    """The form's date was stored as midnight UTC — 5 PM the evening before in
    Los Angeles — and the page then showed back that instant's UTC date."""
    classroom = initialize_as_teacher("tz_pacific_p1", client, app)
    fields = {
        "class_id": classroom.class_id, "title": "Field trip", "message": "Bring lunch",
        "priority": "normal", "is_active": "y", "expires_at": CHOSEN_DAY.isoformat(),
    }
    assert client.post("/admin/announcements/create", data=fields).status_code == 302
    announcement = Announcement.query.filter_by(class_id=classroom.class_id, title="Field trip").one()
    assert announcement.expires_at == END_OF_CHOSEN_DAY_PACIFIC

    listing = client.get("/admin/announcements").get_data(as_text=True)
    assert "Expires: Oct 10, 2030" in listing
    edit = client.get(f"/admin/announcements/edit/{announcement.id}").get_data(as_text=True)
    assert 'value="2030-10-10"' in edit


def test_INV_ARC_015__announcement_created_time_is_class_time(client, app, monkeypatch):
    """23:00 UTC on Sep 25 is 08:00 on Sep 26 in Tokyo."""
    classroom = initialize_as_teacher("tz_tokyo_p1", client, app)
    with _pinned_clock(monkeypatch, _utc(2026, 9, 25, 23, 0)):
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"announcement:{uuid4().hex}"):
            create_class_announcement(
                created_by_seat_id=classroom.teacher_seat.id, class_id=classroom.class_id,
                title="Morning notice", message="Body", priority="normal", is_active=True,
                expires_at=None,
            )
    db.session.commit()

    listing = client.get("/admin/announcements").get_data(as_text=True)
    assert "Sep 26, 2026, 8:00 AM JST" in listing


def test_INV_ARC_015__student_sees_the_chosen_last_day_of_an_announcement(client, app):
    classroom, _student = initialize_as_student("tz_pacific_p1", client, app)
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"announcement:{uuid4().hex}"):
        create_class_announcement(
            created_by_seat_id=classroom.teacher_seat.id, class_id=classroom.class_id,
            title="Field trip", message="Body", priority="normal", is_active=True,
            expires_at=_end_of_day_utc(CHOSEN_DAY, class_id=classroom.class_id),
        )
    db.session.commit()

    dashboard = client.get("/student/dashboard").get_data(as_text=True)
    assert "Expires Oct 10, 2030" in dashboard


# --------------------------------------------------------------------------- #
# Store collective-goal deadline                                               #
# --------------------------------------------------------------------------- #

def test_INV_ARC_015__collective_goal_deadline_shows_the_chosen_day(client, app):
    classroom = initialize_as_teacher("tz_pacific_p1", client, app)
    enable_class_feature(class_id=classroom.class_id, feature="store")
    deadline = _end_of_day_utc(CHOSEN_DAY, class_id=classroom.class_id)
    assert deadline == END_OF_CHOSEN_DAY_PACIFIC
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"goal:{uuid4().hex}"):
        publish_store_product(
            class_id=classroom.class_id, entitlement_type="COLLECTIVE_GOAL",
            created_by_seat_id=classroom.teacher_seat.id, name="Pizza party",
            price="10.00", collective_goal_type="fixed", collective_goal_target=3,
            collective_goal_expires_at=deadline,
        )
    db.session.commit()

    page = client.get("/admin/store").get_data(as_text=True)
    assert "<strong>Deadline:</strong> Oct 10, 2030" in page


# --------------------------------------------------------------------------- #
# Insurance claim form                                                         #
# --------------------------------------------------------------------------- #

def test_INV_ARC_015__claim_date_picker_allows_the_class_today(client, app, monkeypatch):
    """At 08:00 in Tokyo the UTC date is still yesterday; capping the picker at
    it stopped a student from claiming today."""
    classroom, student = initialize_as_student("tz_tokyo_p1", client, app)
    enable_class_feature(class_id=classroom.class_id, feature="insurance")
    teacher = CanonicalContext(
        user_id=classroom.teacher_user.id, class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id, actor_role="teacher",
    )
    policy = configure_insurance_definition(
        class_id=classroom.class_id,
        submission=dict(
            insurance_type="PRODUCTIVITY", premium="10.00", charge_frequency="WEEKLY",
            bill_preview_days=3, nonpayment_mode="ACCUMULATE",
            reimbursement_percentage="80", payout_multiple="5",
            claimable_dates_per_week_equivalent="5", title="Productivity Cover",
        ),
        canonical_context=teacher,
        correlation_id=f"corr_{uuid4().hex}", idempotency_key=f"cfg:{uuid4().hex}",
    )
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"fund:{uuid4().hex}"):
        create_idempotent_transaction(
            idempotency_key=f"fund:{uuid4().hex}", seat_id=student.seat.id,
            class_id=classroom.class_id, target_seat_id=student.seat.id,
            actor_seat_id=student.seat.id, mechanism="self", amount=Decimal("100.00"),
            account_type="checking", type="payroll", description="test funding",
        )
    execute_purchase_insurance(
        canonical_context=CanonicalContext(
            user_id=student.user.id, class_id=classroom.class_id,
            seat_id=student.seat.id, actor_role="student",
        ),
        policy_uuid=policy.policy_uuid, idempotency_key=f"ins:{uuid4().hex}",
    )
    db.session.commit()

    # The next 23:00 UTC after the purchase: 08:00 the following day in Tokyo.
    tokyo_morning = _next_utc_2300(utc_now())
    class_today = _day(CLASS_LEVEL_EVALUATION, tokyo_morning, classroom.class_id)
    assert class_today != _day(SYSTEM_LEVEL_EVALUATION, tokyo_morning)
    with _pinned_clock(monkeypatch, tokyo_morning):
        page = client.get(f"/student/insurance/claim/{policy.policy_uuid}").get_data(as_text=True)

    assert f'max="{class_today.isoformat()}"' in page


def _day(evaluation_type, instant, class_id=None):
    return canonical_temporal_resolver(
        evaluation_type,
        canonical_execution_context=SimpleNamespace(class_id=class_id) if class_id else None,
        primitive="current_evaluation_day",
        reference_time_utc=instant,
    ).evaluation_date


def _next_utc_2300(after):
    def shift(instant, seconds):
        return canonical_temporal_resolver(
            SYSTEM_LEVEL_EVALUATION, primitive="shift_timestamp",
            timestamp=instant, elapsed_seconds=seconds,
        ).shifted_timestamp_utc

    day_start = canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION, primitive="evaluation_day_boundaries", reference_time_utc=after,
    ).boundary_start_utc
    candidate = shift(day_start, 23 * 3600)
    later = canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION, primitive="later_than", candidate=candidate, reference=after,
    ).is_later
    return candidate if later else shift(day_start, 47 * 3600)
