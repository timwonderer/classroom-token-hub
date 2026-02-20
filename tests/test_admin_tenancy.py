import pyotp
from datetime import datetime, timezone

from app import db
from app.models import Admin, Student, StudentTeacher, TeacherBlock, Transaction
from app.hash_utils import get_random_salt, hash_username


def _create_admin(username: str) -> tuple[Admin, str]:
    secret = pyotp.random_base32()
    admin = Admin(username=username, totp_secret=secret)
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
    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher.id))
    db.session.commit()
    return student


def _login_admin(client, admin: Admin, secret: str):
    response = client.post(
        "/admin/login",
        data={"username": admin.username, "totp_code": pyotp.TOTP(secret).now()},
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
    db.session.add(StudentTeacher(student_id=shared_student.id, admin_id=teacher_b.id))
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

    # Teacher has two class contexts; stale session context points to the other student.
    db.session.add_all([
        TeacherBlock(
            teacher_id=teacher.id,
            block="A",
            class_label="A",
            first_name="Alice",
            last_initial="A",
            last_name_hash_by_part=["x"],
            dob_sum=1010,
            salt=get_random_salt(),
            first_half_hash="alice-seat",
            join_code="JOINA",
            student_id=student_a.id,
            is_claimed=True,
        ),
        TeacherBlock(
            teacher_id=teacher.id,
            block="B",
            class_label="B",
            first_name="Bob",
            last_initial="A",
            last_name_hash_by_part=["y"],
            dob_sum=2020,
            salt=get_random_salt(),
            first_half_hash="bob-seat",
            join_code="JOINB",
            student_id=student_b.id,
            is_claimed=True,
        ),
        Transaction(
            student_id=student_a.id,
            amount=25,
            type="bonus",
            account_type="checking",
            description="Scoped tx",
            join_code="JOINA",
        ),
    ])
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
