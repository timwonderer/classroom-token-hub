from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app import db, Student
from werkzeug.security import generate_password_hash
from app.hash_utils import hash_username, get_random_salt
from bs4 import BeautifulSoup
import json

def login(client, username, pin):
    return client.post('/student/login', data={'username': username, 'pin': pin})

def parse_server_state(html):
    soup = BeautifulSoup(html, 'html.parser')
    script = soup.find(id='serverState')
    return json.loads(script.string)

def create_claimed_seat(teacher_id, student_id, block, join_code, salt=None):
    from app.models import TeacherBlock, ClassEconomy, Seat
    if salt is None:
        salt = get_random_salt()

    # Ensure ClassEconomy exists for FK constraint
    class_economy = ClassEconomy.query.filter_by(join_code=join_code).first()
    if not class_economy:
        class_economy = ClassEconomy(join_code=join_code, teacher_id=teacher_id, display_name=f"Class {join_code}")
        db.session.add(class_economy)
        db.session.flush()

    tb = TeacherBlock(
        teacher_id=teacher_id,
        block=block,
        first_name="Test",
        last_initial="S",
        last_name_hash_by_part=None,
        dob_sum_hash=None,
        salt=salt,
        first_half_hash="mock",
        join_code=join_code,
        student_id=student_id,
        is_claimed=True
    )
    db.session.add(tb)
    db.session.flush()

    db.session.add(Seat(
        student_id=student_id,
        class_id=class_economy.class_id,
        join_code=join_code,
        block=block,
        role="student",
    ))
    return tb

def test_dynamic_blocks_and_tap_flow(client):
    from app.models import Admin, StudentTeacher
    import pyotp

    # Create a teacher and link the student
    teacher = make_admin("tapflow-teacher", pyotp.random_base32())
    db.session.add(teacher)
    db.session.flush()

    # 1. Create a two-block student
    salt = get_random_salt()
    username = "t1"
    stu = Student(
        first_name="Test",
        last_initial="S",
        block="A,C",
        salt=salt,
        username_hash=hash_username(username, salt),
        pin_hash=generate_password_hash("0000"),
    )
    db.session.add(stu)
    db.session.flush()

    # Link student to teacher via StudentTeacher
    st = StudentTeacher(student_id=stu.id, teacher_id=teacher.id)
    db.session.add(st)

    # Create TeacherBlocks for the student (required for join_code context)
    create_claimed_seat(teacher.id, stu.id, "A", "JOIN-A", salt)
    create_claimed_seat(teacher.id, stu.id, "C", "JOIN-C", salt)

    db.session.commit()

    # 2. Log in
    resp = login(client, username, "0000")
    assert resp.status_code == 302

    # 3. Dashboard must include the current block (Block A by default)
    # Note: New multi-tenancy model only shows ONE class at a time.
    dash_html = client.get('/student/dashboard').data.decode()
    assert "Period A" in dash_html
    # assert "Block C" in dash_html  <-- Removed: Dashboard only shows current class

    # 4. Tap in to A
    j = client.post('/api/tap', json={'period': 'A', 'action': 'tap_in', 'pin': '0000'})
    assert j.status_code == 200 and j.json['status'] == 'ok'

    # 5. On next dashboard load, A should be “active”
    dash_state = client.get('/student/dashboard').data.decode()
    assert '"A":{"active":true' in dash_state

    # 6. Tap out with “done”
    j2 = client.post('/api/tap', json={'period': 'A', 'action': 'tap_out', 'reason': 'done', 'pin': '0000'})
    assert j2.status_code == 200 and j2.json['status'] == 'ok'

    # 7. After refresh, “done” state must stick
    dash_html2 = client.get('/student/dashboard').data.decode()
    assert '"A":{"active":false,"done":true' in dash_html2

def test_invalid_period_and_action(client):
    from app.models import Admin
    import pyotp

    # Create dummy teacher
    teacher = make_admin("t2_teacher", pyotp.random_base32())
    db.session.add(teacher)
    db.session.flush()

    # Set up student and log in
    salt = get_random_salt()
    username = "t2"
    stu = Student(
        first_name="Test",
        last_initial="S",
        block="A",
        salt=salt,
        username_hash=hash_username(username, salt),
        pin_hash=generate_password_hash("0000"),
    )
    db.session.add(stu)

    # Create TeacherBlock
    create_claimed_seat(teacher.id, stu.id, "A", "JOIN-T2", salt)

    db.session.commit()
    login(client, username, "0000")
    # Invalid period
    resp = client.post('/api/tap', json={'period': 'Z', 'action': 'tap_in', 'pin': '0000'})
    assert resp.status_code == 400
    assert 'error' in resp.json

    # Invalid action
    resp = client.post('/api/tap', json={'period': 'A', 'action': 'jump', 'pin': '0000'})
    assert resp.status_code == 400
    assert 'error' in resp.json

def test_server_state_json(client):
    from app.models import Admin, StudentTeacher
    import pyotp

    # Create a teacher and link the student
    teacher = make_admin("serverstate-teacher", pyotp.random_base32())
    db.session.add(teacher)
    db.session.flush()

    # Ensure serverState JSON matches interactions
    # Create and log in student
    salt = get_random_salt()
    username = "t3"
    stu = Student(
        first_name="Test",
        last_initial="S",
        block="A",
        salt=salt,
        username_hash=hash_username(username, salt),
        pin_hash=generate_password_hash("0000"),
    )
    db.session.add(stu)
    db.session.flush()

    # Link student to teacher via StudentTeacher
    st = StudentTeacher(student_id=stu.id, teacher_id=teacher.id)
    db.session.add(st)

    # Create TeacherBlock
    create_claimed_seat(teacher.id, stu.id, "A", "JOIN-A", salt)

    db.session.commit()

    login(client, username, "0000")

    # Tap in to block A
    client.post('/api/tap', json={'period': 'A', 'action': 'tap_in', 'pin': '0000'})
    dash_html = client.get('/student/dashboard').data.decode()
    state = parse_server_state(dash_html)
    assert 'A' in state
    assert state['A']['active'] is True

    # Tap out with done
    client.post('/api/tap', json={'period': 'A', 'action': 'tap_out', 'reason': 'done', 'pin': '0000'})
    dash_html2 = client.get('/student/dashboard').data.decode()
    state2 = parse_server_state(dash_html2)
    assert state2['A']['active'] is False
    assert state2['A']['done'] is True

def test_auto_tapout_skips_when_join_code_missing(client, caplog):
    """
    Test that auto-tap-out gracefully skips students with legacy TapEvents
    that have no join_code, and logs an appropriate warning.
    """
    from app import TapEvent
    from app.models import Admin, PayrollSettings
    from app.routes.api import check_and_auto_tapout_if_limit_reached
    from datetime import datetime, timezone, timedelta
    import logging
    import pyotp

    # Create teacher and payroll settings with low limit
    teacher = make_admin("legacy_teacher", pyotp.random_base32())
    db.session.add(teacher)
    db.session.flush()

    ps = PayrollSettings(
        teacher_id=teacher.id,
        block="A",
        daily_limit_hours=0.001, # very small limit to trigger immediate tapout
        settings_mode='simple'
    )
    db.session.add(ps)

    # 1. Create a student with a period
    salt = get_random_salt()
    username = "legacy_test"
    stu = Student(
        first_name="Legacy",
        last_initial="T",
        block="A",
        salt=salt,
        username_hash=hash_username(username, salt),
        pin_hash=generate_password_hash("0000"),
    )
    db.session.add(stu)
    db.session.flush()
    
    # Link to teacher
    from app.models import StudentTeacher
    st = StudentTeacher(student_id=stu.id, teacher_id=teacher.id)
    db.session.add(st)
    
    db.session.commit()

    # 2. Create a legacy TapEvent without join_code (simulating old data)
    # Backdate it to ensure it exceeds the limit
    legacy_event = TapEvent(
        student_id=stu.id,
        period="A",
        status="active",
        timestamp=datetime.now(timezone.utc) - timedelta(hours=1),
        join_code=None  # Explicitly no join_code
    )
    db.session.add(legacy_event)
    db.session.commit()

    # 3. Count TapEvents before auto-tap-out
    events_before = TapEvent.query.filter_by(student_id=stu.id, period="A").count()

    # 4. Call auto-tap-out function with logging enabled
    with caplog.at_level(logging.WARNING):
        check_and_auto_tapout_if_limit_reached(stu)

    # 5. Count TapEvents after - should be same (no new tap-out event created)
    events_after = TapEvent.query.filter_by(student_id=stu.id, period="A").count()
    assert events_before == events_after, "Auto-tap-out should skip when join_code cannot be resolved"

    # 6. Verify warning was logged with TapEvent ID
    assert any(
        "Unable to resolve join_code" in record.message and
        f"TapEvent ID is {legacy_event.id}" in record.message
        for record in caplog.records
    ), f"Expected warning about missing join_code was not logged. Records: {[r.message for r in caplog.records]}"


def test_student_status_get_is_read_only_and_reconcile_is_explicit_mutation(client, monkeypatch):
    from datetime import datetime, timezone
    from app.models import Admin, StudentTeacher, ClassEconomy, Seat
    import pyotp
    from app.routes import api as api_routes

    teacher = make_admin("status_teacher", pyotp.random_base32())
    db.session.add(teacher)
    db.session.flush()

    salt = get_random_salt()
    username = "status_student"
    stu = Student(
        first_name="Status",
        last_initial="R",
        block="A",
        salt=salt,
        username_hash=hash_username(username, salt),
        pin_hash=generate_password_hash("0000"),
    )
    db.session.add(stu)
    db.session.flush()

    db.session.add(StudentTeacher(student_id=stu.id, teacher_id=teacher.id))
    create_claimed_seat(teacher.id, stu.id, "A", "JOIN-A", salt)
    db.session.commit()
    class_row = ClassEconomy.query.filter_by(join_code="JOIN-A").first()
    seat = Seat.query.filter_by(student_id=stu.id, class_id=class_row.class_id).first()
    assert class_row is not None
    assert seat is not None
    if not seat.claimed_at:
        seat.claimed_at = datetime.now(timezone.utc)
        db.session.commit()

    with client.session_transaction() as sess:
        now = datetime.now(timezone.utc).isoformat()
        sess["student_id"] = stu.id
        sess["current_seat_id"] = seat.id
        sess["seat_id"] = seat.id
        sess["current_class_id"] = class_row.class_id
        sess["class_id"] = class_row.class_id
        sess["current_join_code"] = "JOIN-A"
        sess["login_time"] = now
        sess["last_activity"] = now

    called = {"count": 0}

    def _fake_auto_tapout(student, commit=True):
        called["count"] += 1

    monkeypatch.setattr(api_routes, "check_and_auto_tapout_if_limit_reached", _fake_auto_tapout)

    get_resp = client.get("/api/student-status")
    assert get_resp.status_code == 200
    assert called["count"] == 0

    post_resp = client.post("/api/student-status/reconcile")
    assert post_resp.status_code == 200
    assert called["count"] == 1
