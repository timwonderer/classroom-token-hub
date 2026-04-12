from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pyotp
import re
from datetime import datetime, timezone, timedelta

from app import db
from app.models import Admin, Student, StudentTeacher, TeacherBlock, Transaction, TapEvent, StudentBlock, PayrollSettings, User, Seat
from app.hash_utils import get_random_salt, hash_username
from tests.helpers.class_scope import create_class_scope


def _create_admin(username: str) -> tuple[Admin, str]:
    secret = pyotp.random_base32()
    admin = make_admin(username, secret)
    db.session.add(admin)
    db.session.commit()
    return admin, secret


def _create_student(first_name: str, teacher: Admin) -> Student:
    salt = get_random_salt()
    student = Student(
        first_name=first_name,
        last_initial="A",
        block="A",
        salt=salt,
        username_hash=hash_username(first_name.lower(), salt),
        pin_hash="pin",
    )
    db.session.add(student)
    db.session.flush()
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    db.session.commit()
    return student


def _login_admin(client, admin: Admin, secret: str):
    response = client.post(
        "/admin/login",
        data={"username": "teacher1", "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )
    with client.session_transaction() as sess:
        sess.setdefault("is_admin", True)
        sess.setdefault("admin_id", admin.id)
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()
    return response


def test_student_listing_scoped_to_teacher(client):
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, secret_b = _create_admin("teacher-b")
    student_a = _create_student("Alice", teacher_a)
    _create_student("Bob", teacher_b)

    _login_admin(client, teacher_a, secret_a)

    response = client.get("/admin/students")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert student_a.first_name in body
    assert "Bob" not in body


def test_student_detail_forbids_cross_tenant_access(client):
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, secret_b = _create_admin("teacher-b")
    _create_student("Alice", teacher_a)
    student_b = _create_student("Bob", teacher_b)

    _login_admin(client, teacher_a, secret_a)

    response = client.get(f"/admin/students/{student_b.id}")

    assert response.status_code == 404


def test_shared_student_accessible_to_multiple_teachers(client):
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, secret_b = _create_admin("teacher-b")
    shared_student = _create_student("Shared", teacher_a)

    # Grant teacher B access to the shared student without changing the primary teacher
    db.session.add(StudentTeacher(student_id=shared_student.id, teacher_id=teacher_b.id))
    db.session.commit()

    _login_admin(client, teacher_b, secret_b)

    detail_response = client.get(f"/admin/students/{shared_student.id}")
    list_response = client.get("/admin/students")

    assert detail_response.status_code == 200
    assert "Shared" in list_response.get_data(as_text=True)


def test_student_detail_recovers_from_stale_class_context(client):
    teacher, secret = _create_admin("teacher-a")
    student_a = _create_student("Alice", teacher)
    student_b = _create_student("Bob", teacher)

    class_a = create_class_scope(
        teacher=teacher,
        join_code="JOINA",
        student=student_a,
        block="A",
        display_name="A",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    class_b = create_class_scope(
        teacher=teacher,
        join_code="JOINB",
        student=student_b,
        block="B",
        display_name="B",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    db.session.flush()
    seat_a = Seat.query.filter_by(student_id=student_a.id, join_code="JOINA", class_id=class_a.class_id).first()
    assert seat_a is not None
    Seat.query.filter_by(student_id=student_b.id, join_code="JOINB", class_id=class_b.class_id).first()

    # Teacher has two class contexts; stale session context points to the other student.
    db.session.add(
        Transaction(
            student_id=student_a.id,
            seat_id=seat_a.id,
            amount=25,
            type="bonus",
            account_type="checking",
            description="Scoped tx",
            join_code="JOINA",
        ),
    )
    db.session.commit()

    _login_admin(client, teacher, secret)
    with client.session_transaction() as sess:
        sess["current_join_code"] = "JOINB"

    response = client.get(f"/admin/students/{student_a.id}")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Scoped tx" in body

    with client.session_transaction() as sess:
        assert sess["current_join_code"] == "JOINA"


def test_tap_out_students_rejects_cross_scope_student_block(client):
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")
    shared_student = _create_student("Shared", teacher_a)
    db.session.add(StudentTeacher(student_id=shared_student.id, teacher_id=teacher_b.id))

    db.session.add_all([
        TeacherBlock(
            teacher_id=teacher_a.id,
            block="A",
            class_label="A",
            first_name="Shared",
            last_initial="A",
            last_name_hash_by_part=["x"],
            dob_sum_hash=None,
            salt=get_random_salt(),
            first_half_hash="shared-a-seat",
            join_code="JOINA",
            student_id=shared_student.id,
            is_claimed=True,
        ),
        TeacherBlock(
            teacher_id=teacher_b.id,
            block="A",
            class_label="A",
            first_name="Shared",
            last_initial="A",
            last_name_hash_by_part=["y"],
            dob_sum_hash=None,
            salt=get_random_salt(),
            first_half_hash="shared-b-seat",
            join_code="JOINB",
            student_id=shared_student.id,
            is_claimed=True,
        ),
        TapEvent(
            student_id=shared_student.id,
            period="A",
            status="active",
            join_code="JOINA",
            reason="Start work",
        ),
        StudentBlock(
            student_id=shared_student.id,
            period="A",
            join_code="JOINB",
            tap_enabled=True,
        ),
    ])
    db.session.commit()

    _login_admin(client, teacher_a, secret_a)
    response = client.post(
        "/admin/tap-out-students",
        json={"student_ids": [shared_student.id], "period": "A", "reason": "Teacher tap-out"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["tapped_out"] == []
    assert any("different class scope" in msg for msg in payload["errors"])

    block = StudentBlock.query.filter_by(student_id=shared_student.id, period="A").first()
    assert block is not None
    assert block.join_code == "JOINB"
    assert block.done_for_day_date is None

    inactive_count = TapEvent.query.filter_by(
        student_id=shared_student.id,
        period="A",
        status="inactive",
        join_code="JOINA",
    ).count()
    assert inactive_count == 0


def test_tap_out_students_rejects_null_join_code_student_block(client):
    teacher, secret = _create_admin("teacher-a")
    student = _create_student("Alice", teacher)

    db.session.add_all([
        TeacherBlock(
            teacher_id=teacher.id,
            block="A",
            class_label="A",
            first_name="Alice",
            last_initial="A",
            last_name_hash_by_part=["x"],
            dob_sum_hash=None,
            salt=get_random_salt(),
            first_half_hash="alice-seat",
            join_code="JOINA",
            student_id=student.id,
            is_claimed=True,
        ),
        TapEvent(
            student_id=student.id,
            period="A",
            status="active",
            join_code="JOINA",
            reason="Start work",
        ),
        StudentBlock(
            student_id=student.id,
            period="A",
            join_code=None,
            tap_enabled=True,
        ),
    ])
    db.session.commit()

    _login_admin(client, teacher, secret)
    response = client.post(
        "/admin/tap-out-students",
        json={"student_ids": [student.id], "period": "A", "reason": "Teacher tap-out"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["tapped_out"] == []
    assert any("missing class scope" in msg for msg in payload["errors"])

    block = StudentBlock.query.filter_by(student_id=student.id, period="A").first()
    assert block is not None
    assert block.join_code is None
    assert block.done_for_day_date is None

    inactive_count = TapEvent.query.filter_by(
        student_id=student.id,
        period="A",
        status="inactive",
        join_code="JOINA",
    ).count()
    assert inactive_count == 0


def test_tap_in_students_rejects_cross_scope_student_block(client):
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")
    shared_student = _create_student("SharedIn", teacher_a)
    db.session.add(StudentTeacher(student_id=shared_student.id, teacher_id=teacher_b.id))

    db.session.add_all([
        TeacherBlock(
            teacher_id=teacher_a.id,
            block="A",
            class_label="A",
            first_name="SharedIn",
            last_initial="A",
            last_name_hash_by_part=["x"],
            dob_sum_hash=None,
            salt=get_random_salt(),
            first_half_hash="shared-in-a-seat",
            join_code="JOINA",
            student_id=shared_student.id,
            is_claimed=True,
        ),
        TeacherBlock(
            teacher_id=teacher_b.id,
            block="A",
            class_label="A",
            first_name="SharedIn",
            last_initial="A",
            last_name_hash_by_part=["y"],
            dob_sum_hash=None,
            salt=get_random_salt(),
            first_half_hash="shared-in-b-seat",
            join_code="JOINB",
            student_id=shared_student.id,
            is_claimed=True,
        ),
        TapEvent(
            student_id=shared_student.id,
            period="A",
            status="inactive",
            join_code="JOINA",
            reason="Teacher tap-out",
        ),
        StudentBlock(
            student_id=shared_student.id,
            period="A",
            join_code="JOINB",
            tap_enabled=True,
        ),
    ])
    db.session.commit()

    _login_admin(client, teacher_a, secret_a)
    response = client.post(
        "/admin/tap-in-students",
        json={"student_ids": [shared_student.id], "period": "A"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["tapped_in"] == []
    assert any("different class scope" in msg for msg in payload["errors"])

    block = StudentBlock.query.filter_by(student_id=shared_student.id, period="A").first()
    assert block is not None
    assert block.join_code == "JOINB"

    active_count = TapEvent.query.filter_by(
        student_id=shared_student.id,
        period="A",
        status="active",
        join_code="JOINA",
    ).count()
    assert active_count == 0


def test_tap_in_students_rejects_null_join_code_student_block(client):
    teacher, secret = _create_admin("teacher-a")
    student = _create_student("AliceIn", teacher)

    db.session.add_all([
        TeacherBlock(
            teacher_id=teacher.id,
            block="A",
            class_label="A",
            first_name="AliceIn",
            last_initial="A",
            last_name_hash_by_part=["x"],
            dob_sum_hash=None,
            salt=get_random_salt(),
            first_half_hash="alice-in-seat",
            join_code="JOINA",
            student_id=student.id,
            is_claimed=True,
        ),
        TapEvent(
            student_id=student.id,
            period="A",
            status="inactive",
            join_code="JOINA",
            reason="Teacher tap-out",
        ),
        StudentBlock(
            student_id=student.id,
            period="A",
            join_code=None,
            tap_enabled=True,
            done_for_day_date=datetime.now(timezone.utc).date(),
        ),
    ])
    db.session.commit()

    _login_admin(client, teacher, secret)
    response = client.post(
        "/admin/tap-in-students",
        json={"student_ids": [student.id], "period": "A"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["tapped_in"] == []
    assert any("missing class scope" in msg for msg in payload["errors"])

    block = StudentBlock.query.filter_by(student_id=student.id, period="A").first()
    assert block is not None
    assert block.join_code is None
    assert block.done_for_day_date is not None

    active_count = TapEvent.query.filter_by(
        student_id=student.id,
        period="A",
        status="active",
        join_code="JOINA",
    ).count()
    assert active_count == 0


def test_enforce_daily_limits_ignores_other_join_code_activity(client):
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")
    shared_student = _create_student("SharedLimit", teacher_a)
    db.session.add(StudentTeacher(student_id=shared_student.id, teacher_id=teacher_b.id))

    db.session.add_all([
        TeacherBlock(
            teacher_id=teacher_a.id,
            block="A",
            class_label="A",
            first_name="SharedLimit",
            last_initial="A",
            last_name_hash_by_part=["x"],
            dob_sum_hash=None,
            salt=get_random_salt(),
            first_half_hash="shared-limit-a-seat",
            join_code="JOINA",
            student_id=shared_student.id,
            is_claimed=True,
        ),
        TeacherBlock(
            teacher_id=teacher_b.id,
            block="A",
            class_label="A",
            first_name="SharedLimit",
            last_initial="A",
            last_name_hash_by_part=["y"],
            dob_sum_hash=None,
            salt=get_random_salt(),
            first_half_hash="shared-limit-b-seat",
            join_code="JOINB",
            student_id=shared_student.id,
            is_claimed=True,
        ),
        PayrollSettings(
            teacher_id=teacher_a.id,
            block="A",
            is_active=True,
            settings_mode="simple",
            daily_limit_hours=0.001,  # ~3.6 seconds
            pay_rate=0.25,
            payroll_frequency_days=14,
        ),
        TapEvent(
            student_id=shared_student.id,
            period="A",
            status="active",
            join_code="JOINB",
            reason="Start work",
            timestamp=datetime.now(timezone.utc) - timedelta(hours=2),
        ),
    ])
    db.session.commit()

    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = teacher_a.id
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()
    response = client.post("/admin/enforce-daily-limits")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["checked"] == 0
    assert payload["tapped_out"] == []

    inactive_count = TapEvent.query.filter_by(
        student_id=shared_student.id,
        period="A",
        status="inactive",
        join_code="JOINA",
    ).count()
    assert inactive_count == 0


def test_enforce_daily_limits_taps_out_when_limit_reached_in_scope(client):
    teacher, secret = _create_admin("teacher-a")
    student = _create_student("AliceLimit", teacher)

    class_scope = create_class_scope(
        teacher=teacher,
        join_code="JOINA",
        student=student,
        block="A",
        display_name="A",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    db.session.flush()
    seat = Seat.query.filter_by(student_id=student.id, join_code="JOINA", class_id=class_scope.class_id).first()
    assert seat is not None

    db.session.add_all([
        PayrollSettings(
            teacher_id=teacher.id,
            join_code="JOINA",
            class_id=class_scope.class_id,
            block="A",
            is_active=True,
            settings_mode="simple",
            daily_limit_hours=0.001,
            pay_rate=0.25,
            payroll_frequency_days=14,
        ),
        TapEvent(
            student_id=student.id,
            seat_id=seat.id,
            period="A",
            status="active",
            join_code="JOINA",
            reason="Start work",
            timestamp=datetime.now(timezone.utc) - timedelta(hours=2),
        ),
    ])
    db.session.commit()

    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = teacher.id
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()
    response = client.post("/admin/enforce-daily-limits")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["checked"] >= 1
    assert any(student.full_name in entry for entry in payload["tapped_out"])

    block = StudentBlock.query.filter_by(student_id=student.id, period="A").first()
    assert block is not None
    assert block.join_code == "JOINA"
    assert block.done_for_day_date is not None

    inactive_count = TapEvent.query.filter(
        TapEvent.student_id == student.id,
        TapEvent.period == "A",
        TapEvent.status == "inactive",
        TapEvent.join_code == "JOINA",
        TapEvent.reason.ilike("Daily limit%"),
    ).count()
    assert inactive_count == 1


def test_student_detail_ignores_student_block_from_other_join_code(client):
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")
    shared_student = _create_student("SharedDetail", teacher_a)
    db.session.add(StudentTeacher(student_id=shared_student.id, teacher_id=teacher_b.id))

    db.session.add_all([
        TeacherBlock(
            teacher_id=teacher_a.id,
            block="A",
            class_label="A",
            first_name="SharedDetail",
            last_initial="A",
            last_name_hash_by_part=["x"],
            dob_sum_hash=None,
            salt=get_random_salt(),
            first_half_hash="shared-detail-a-seat",
            join_code="JOINA",
            student_id=shared_student.id,
            is_claimed=True,
        ),
        TeacherBlock(
            teacher_id=teacher_b.id,
            block="A",
            class_label="A",
            first_name="SharedDetail",
            last_initial="A",
            last_name_hash_by_part=["y"],
            dob_sum_hash=None,
            salt=get_random_salt(),
            first_half_hash="shared-detail-b-seat",
            join_code="JOINB",
            student_id=shared_student.id,
            is_claimed=True,
        ),
        StudentBlock(
            student_id=shared_student.id,
            period="A",
            join_code="JOINB",
            tap_enabled=False,
        ),
    ])
    db.session.commit()

    _login_admin(client, teacher_a, secret_a)
    response = client.get(f"/admin/students/{shared_student.id}?join_code=JOINA")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="tapToggleA"' in body
    assert re.search(r'<input[^>]*id="tapToggleA"[^>]*checked', body) is not None


def test_edit_student_transfer_updates_transaction_seat_scope(client):
    teacher, secret = _create_admin("teacher-a")
    student = _create_student("TransferSeat", teacher)

    db.session.add_all([
        TeacherBlock(
            teacher_id=teacher.id,
            block="A",
            class_label="A",
            first_name="TransferSeat",
            last_initial="A",
            last_name_hash_by_part=["x"],
            dob_sum_hash=None,
            salt=get_random_salt(),
            first_half_hash="transfer-seat-a",
            join_code="JOINA",
            student_id=student.id,
            is_claimed=True,
        ),
        TeacherBlock(
            teacher_id=teacher.id,
            block="B",
            class_label="B",
            first_name="TransferSeat",
            last_initial="A",
            last_name_hash_by_part=["y"],
            dob_sum_hash=None,
            salt=get_random_salt(),
            first_half_hash="transfer-seat-b",
            join_code="JOINB",
            student_id=student.id,
            is_claimed=True,
        ),
    ])
    db.session.flush()

    user = User(
        username="transfer-seat-user",
        password_hash="pw",
    )
    db.session.add(user)
    db.session.flush()

    seat_a = Seat(user_id=user.id, student_id=student.id, join_code="JOINA", block="A")
    seat_b = Seat(user_id=user.id, student_id=student.id, join_code="JOINB", block="B")
    db.session.add_all([seat_a, seat_b])
    db.session.flush()

    tx = Transaction(
        student_id=student.id,
        seat_id=seat_a.id,
        join_code="JOINA",
        amount=10,
        account_type="checking",
        type="bonus",
        description="pre-transfer",
    )
    db.session.add(tx)
    db.session.commit()

    _login_admin(client, teacher, secret)
    response = client.post(
        "/admin/student/edit",
        data={
            "student_id": student.id,
            "first_name": "TransferSeat",
            "last_name": "A",
            "blocks": ["B"],
            "balance_action_B": "transfer",
        },
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)
    db.session.refresh(tx)
    assert tx.join_code == "JOINB"
    assert tx.seat_id == seat_b.id
