"""
Route-level tests for the add_rent_waiver admin endpoint.

Covers:
- past_due scope: creates one RentWaiver per selected date
- current scope: creates one RentWaiver for the current coverage date
- future scope: creates one RentWaiver spanning N upcoming periods
- combined scopes: all three scopes together in a single submission
- join_code scoping: waivers are stamped with the session join_code
- invalid future_periods_count: flashes an error instead of 500-ing
- missing join_code: fails fast with a validation error
- invalid past_due_dates: invalid dates are skipped with accurate count in success message
"""
import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import pytest

from app import db
from app.models import (
    Admin,
    AnalyticsEvent,
    RentSettings,
    RentWaiver,
    Student,
    StudentTeacher,
    TeacherBlock,
)
from app.hash_utils import get_random_salt, hash_username


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_admin(suffix):
    admin = Admin(username=f"admin_arw_{suffix}", totp_secret="TESTSECRET123456")
    db.session.add(admin)
    db.session.flush()
    return admin


def _make_teacher_block(admin_id, block, join_code):
    salt = get_random_salt()
    tb = TeacherBlock(
        teacher_id=admin_id,
        block=block,
        first_name="Teacher",
        last_initial="T",
        dob_sum=2000,
        salt=salt,
        first_half_hash="teac",
        last_name_hash_by_part=[],
        join_code=join_code,
        is_claimed=False,
        is_teacher=True,
    )
    db.session.add(tb)
    db.session.flush()
    return tb


def _make_rent_settings(admin_id, block, first_due, frequency_type="weekly"):
    """Create rent settings with a known first_rent_due_date for deterministic date math."""
    settings = RentSettings(
        teacher_id=admin_id,
        block=block,
        is_enabled=True,
        rent_amount=Decimal("50.00"),
        frequency_type=frequency_type,
        grace_period_days=3,
        late_penalty_amount=Decimal("5.00"),
        late_penalty_type="once",
        first_rent_due_date=first_due,
    )
    db.session.add(settings)
    db.session.flush()
    return settings


def _make_student(suffix, block="A"):
    salt = get_random_salt()
    student = Student(
        first_name="Test",
        last_initial="W",
        block=block,
        salt=salt,
        username_hash=hash_username(f"student_arw_{suffix}", salt),
        pin_hash="test-pin",
    )
    db.session.add(student)
    db.session.flush()
    return student


def _link_student(student, admin):
    db.session.add(StudentTeacher(student_id=student.id, admin_id=admin.id))
    db.session.flush()


def _login_admin(client, admin_id, join_code):
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin_id
        sess['current_join_code'] = join_code
        sess['is_system_admin'] = False
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_past_due_scope_creates_one_waiver_per_date(client, app):
    """Selecting past_due scope creates one RentWaiver per submitted date."""
    with app.app_context():
        admin = _make_admin("pd1")
        join_code = "ARW_PD1"
        # Use a weekly cadence so dates are deterministic
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)  # Monday
        _make_rent_settings(admin.id, "A", first_due)
        _make_teacher_block(admin.id, "A", join_code)
        student = _make_student("pd1_s")
        _link_student(student, admin)
        db.session.commit()

        _login_admin(client, admin.id, join_code)

        date1 = datetime(2026, 1, 5, tzinfo=timezone.utc).isoformat()
        date2 = datetime(2026, 1, 12, tzinfo=timezone.utc).isoformat()

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                'student_ids': [str(student.id)],
                'waiver_scope': ['past_due'],
                'past_due_dates': [date1, date2],
                'settings_block': 'A',
            },
        )
        assert resp.status_code == 302

        waivers = RentWaiver.query.filter_by(
            student_id=student.id, join_code=join_code
        ).all()
        assert len(waivers) == 2
        # Each waiver should be a point-in-time entry (start == end, periods_count == 1)
        for w in waivers:
            assert w.waiver_start_date == w.waiver_end_date
            assert w.periods_count == 1


def test_current_scope_creates_waiver_for_current_period(client, app):
    """Selecting current scope creates one RentWaiver covering the current coverage date."""
    with app.app_context():
        admin = _make_admin("cur1")
        join_code = "ARW_CUR1"
        # Set first_rent_due_date in the past so there is an active coverage period
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        _make_rent_settings(admin.id, "A", first_due)
        _make_teacher_block(admin.id, "A", join_code)
        student = _make_student("cur1_s")
        _link_student(student, admin)
        db.session.commit()

        _login_admin(client, admin.id, join_code)

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                'student_ids': [str(student.id)],
                'waiver_scope': ['current'],
                'settings_block': 'A',
            },
        )
        assert resp.status_code == 302

        waivers = RentWaiver.query.filter_by(
            student_id=student.id, join_code=join_code
        ).all()
        # Exactly one waiver for the current period
        assert len(waivers) == 1
        w = waivers[0]
        assert w.periods_count == 1
        assert w.join_code == join_code


def test_future_scope_creates_waiver_spanning_n_periods(client, app):
    """Selecting future scope creates one RentWaiver spanning future_periods_count periods."""
    with app.app_context():
        admin = _make_admin("fut1")
        join_code = "ARW_FUT1"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        _make_rent_settings(admin.id, "A", first_due)
        _make_teacher_block(admin.id, "A", join_code)
        student = _make_student("fut1_s")
        _link_student(student, admin)
        db.session.commit()

        _login_admin(client, admin.id, join_code)

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                'student_ids': [str(student.id)],
                'waiver_scope': ['future'],
                'future_periods_count': '3',
                'settings_block': 'A',
            },
        )
        assert resp.status_code == 302

        waivers = RentWaiver.query.filter_by(
            student_id=student.id, join_code=join_code
        ).all()
        assert len(waivers) == 1
        w = waivers[0]
        assert w.periods_count == 3
        # The future window should span more than one week (since frequency is weekly)
        assert w.waiver_end_date > w.waiver_start_date
        assert w.join_code == join_code


def test_all_scopes_combined_creates_multiple_waivers(client, app):
    """Submitting all three scopes creates multiple waiver rows per student."""
    with app.app_context():
        admin = _make_admin("all1")
        join_code = "ARW_ALL1"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        _make_rent_settings(admin.id, "A", first_due)
        _make_teacher_block(admin.id, "A", join_code)
        student = _make_student("all1_s")
        _link_student(student, admin)
        db.session.commit()

        _login_admin(client, admin.id, join_code)

        past_date = datetime(2026, 1, 5, tzinfo=timezone.utc).isoformat()

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                'student_ids': [str(student.id)],
                'waiver_scope': ['past_due', 'current', 'future'],
                'past_due_dates': [past_date],
                'future_periods_count': '2',
                'settings_block': 'A',
            },
        )
        assert resp.status_code == 302

        waivers = RentWaiver.query.filter_by(
            student_id=student.id, join_code=join_code
        ).all()
        # Expect 3 waiver rows: 1 past-due + 1 current + 1 future
        assert len(waivers) == 3
        period_counts = sorted(w.periods_count for w in waivers)
        assert 1 in period_counts  # past-due and/or current
        assert 2 in period_counts  # future (2 periods)


def test_waivers_stamped_with_join_code(client, app):
    """All created waivers carry the session join_code, not None."""
    with app.app_context():
        admin = _make_admin("jc1")
        join_code = "ARW_JC1"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        _make_rent_settings(admin.id, "A", first_due)
        _make_teacher_block(admin.id, "A", join_code)
        student = _make_student("jc1_s")
        _link_student(student, admin)
        db.session.commit()

        _login_admin(client, admin.id, join_code)

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                'student_ids': [str(student.id)],
                'waiver_scope': ['current'],
                'settings_block': 'A',
            },
        )
        assert resp.status_code == 302

        waivers = RentWaiver.query.filter_by(student_id=student.id).all()
        assert all(w.join_code == join_code for w in waivers)


def test_invalid_future_periods_count_flashes_error(client, app):
    """A non-numeric future_periods_count flashes a validation error instead of raising 500."""
    with app.app_context():
        admin = _make_admin("fp1")
        join_code = "ARW_FP1"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        _make_rent_settings(admin.id, "A", first_due)
        _make_teacher_block(admin.id, "A", join_code)
        student = _make_student("fp1_s")
        _link_student(student, admin)
        db.session.commit()

        _login_admin(client, admin.id, join_code)

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                'student_ids': [str(student.id)],
                'waiver_scope': ['future'],
                'future_periods_count': 'not_a_number',
                'settings_block': 'A',
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b'positive whole number' in resp.data

        # No waivers should have been created
        count = RentWaiver.query.filter_by(student_id=student.id).count()
        assert count == 0


def test_missing_join_code_flashes_error(client, app):
    """If no join_code can be resolved the route redirects with a flash error."""
    with app.app_context():
        admin = _make_admin("nojc1")
        # Intentionally do NOT create a TeacherBlock so join_code cannot be resolved.
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        _make_rent_settings(admin.id, "A", first_due)
        student = _make_student("nojc1_s")
        _link_student(student, admin)
        db.session.commit()

        # Log in without a current_join_code in the session.
        with client.session_transaction() as sess:
            sess['is_admin'] = True
            sess['admin_id'] = admin.id
            sess['is_system_admin'] = False
            sess['last_activity'] = datetime.now(timezone.utc).isoformat()
            # Intentionally omit current_join_code

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                'student_ids': [str(student.id)],
                'waiver_scope': ['current'],
                'settings_block': 'A',  # No TeacherBlock exists for this block
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b'join code' in resp.data.lower() or b'Unable to resolve' in resp.data

        count = RentWaiver.query.filter_by(student_id=student.id).count()
        assert count == 0


def test_invalid_past_due_dates_skipped_count_reflects_actual(client, app):
    """Invalid ISO date strings in past_due_dates are silently skipped;
    success message reflects only the dates that were actually persisted."""
    with app.app_context():
        admin = _make_admin("pd2")
        join_code = "ARW_PD2"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        _make_rent_settings(admin.id, "A", first_due)
        _make_teacher_block(admin.id, "A", join_code)
        student = _make_student("pd2_s")
        _link_student(student, admin)
        db.session.commit()

        _login_admin(client, admin.id, join_code)

        valid_date = datetime(2026, 1, 5, tzinfo=timezone.utc).isoformat()

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                'student_ids': [str(student.id)],
                'waiver_scope': ['past_due'],
                'past_due_dates': [valid_date, 'NOT_A_DATE', ''],
                'settings_block': 'A',
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200

        # Only the valid date should have been persisted
        waivers = RentWaiver.query.filter_by(
            student_id=student.id, join_code=join_code
        ).all()
        assert len(waivers) == 1
        # Flash message should report 1 past-due period (not 3)
        assert b'1 past-due period' in resp.data


def test_add_rent_waiver_logs_analytics_event(client, app, monkeypatch):
    """Adding a rent waiver creates one AnalyticsEvent per student with type 'rent_waiver'."""
    with app.app_context():
        admin = _make_admin("evt1")
        join_code = "ARW_EVT1"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        _make_rent_settings(admin.id, "A", first_due)
        _make_teacher_block(admin.id, "A", join_code)
        student = _make_student("evt1_s")
        _link_student(student, admin)
        db.session.commit()

        fixed_now = datetime(2026, 2, 1, tzinfo=timezone.utc)
        monkeypatch.setattr('app.routes.admin.utc_now', lambda: fixed_now)
        _login_admin(client, admin.id, join_code)

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                'student_ids': [str(student.id)],
                'waiver_scope': ['current'],
                'settings_block': 'A',
                'reason': 'Medical absence',
            },
        )
        assert resp.status_code == 302

        events = AnalyticsEvent.query.filter_by(
            join_code=join_code, event_type='rent_waiver'
        ).all()
        assert len(events) == 1
        event = events[0]
        assert event.teacher_id == admin.id
        assert student.full_name in event.description
        assert event.created_by_admin is True
        assert 'Medical absence' in event.description


def test_add_rent_waiver_logs_one_event_per_student(client, app, monkeypatch):
    """Adding a waiver for multiple students logs one AnalyticsEvent per student."""
    with app.app_context():
        admin = _make_admin("evt2")
        join_code = "ARW_EVT2"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        _make_rent_settings(admin.id, "A", first_due)
        _make_teacher_block(admin.id, "A", join_code)
        student_a = _make_student("evt2_sa")
        student_b = _make_student("evt2_sb")
        _link_student(student_a, admin)
        _link_student(student_b, admin)
        db.session.commit()

        fixed_now = datetime(2026, 2, 1, tzinfo=timezone.utc)
        monkeypatch.setattr('app.routes.admin.utc_now', lambda: fixed_now)
        _login_admin(client, admin.id, join_code)

        resp = client.post(
            '/admin/rent-waiver/add',
            data={
                'student_ids': [str(student_a.id), str(student_b.id)],
                'waiver_scope': ['current'],
                'settings_block': 'A',
            },
        )
        assert resp.status_code == 302

        events = AnalyticsEvent.query.filter_by(
            join_code=join_code, event_type='rent_waiver'
        ).all()
        assert len(events) == 2


def test_remove_rent_waiver_logs_analytics_event(client, app):
    """Removing a rent waiver creates an AnalyticsEvent with type 'rent_waiver'."""
    with app.app_context():
        admin = _make_admin("rem1")
        join_code = "ARW_REM1"
        first_due = datetime(2026, 1, 5, tzinfo=timezone.utc)
        _make_rent_settings(admin.id, "A", first_due)
        _make_teacher_block(admin.id, "A", join_code)
        student = _make_student("rem1_s")
        _link_student(student, admin)
        coverage = datetime(2026, 3, 1, tzinfo=timezone.utc)
        waiver = RentWaiver(
            student_id=student.id,
            join_code=join_code,
            waiver_start_date=coverage,
            waiver_end_date=coverage,
            periods_count=1,
            created_by_admin_id=admin.id,
        )
        db.session.add(waiver)
        db.session.commit()

        _login_admin(client, admin.id, join_code)

        resp = client.post(f'/admin/rent-waiver/{waiver.id}/remove')
        assert resp.status_code == 302

        events = AnalyticsEvent.query.filter_by(
            join_code=join_code, event_type='rent_waiver'
        ).all()
        assert len(events) == 1
        assert student.full_name in events[0].description
        assert 'removed' in events[0].description
