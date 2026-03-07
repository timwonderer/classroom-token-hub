import csv
from io import StringIO

from app import db
from app.hash_utils import get_random_salt, hash_username
from app.models import Admin, Student, StudentTeacher, TeacherBlock, Transaction


def _create_admin(username: str) -> Admin:
    admin = Admin(username=username, totp_secret="TESTSECRET123456")
    db.session.add(admin)
    db.session.commit()
    return admin


def _create_student(first_name: str, teacher: Admin) -> Student:
    salt = get_random_salt()
    student = Student(
        first_name=first_name,
        last_initial="T",
        block="A",
        salt=salt,
        username_hash=hash_username(first_name.lower(), salt),
        pin_hash="fake-hash",
    )
    db.session.add(student)
    db.session.flush()
    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher.id))
    db.session.commit()
    return student


def _add_claimed_seat(admin: Admin, student: Student, block: str, join_code: str):
    seat = TeacherBlock(
        teacher_id=admin.id,
        block=block,
        class_label=block,
        first_name=student.first_name,
        last_initial=student.last_initial,
        last_name_hash_by_part=None,
        dob_sum_hash=None,
        salt=b"seat-salt",
        first_half_hash=f"seat-{admin.id}-{student.id}-{join_code}",
        join_code=join_code,
        student_id=student.id,
        is_claimed=True,
    )
    db.session.add(seat)
    db.session.commit()
    return seat


def _as_admin_session(client, admin: Admin):
    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = admin.id


def test_export_students_scopes_students_and_balances_by_join_code(client):
    admin = _create_admin("export-admin")
    student_a = _create_student("Alice", admin)
    student_b = _create_student("Bob", admin)

    _add_claimed_seat(admin, student_a, "A", "JOIN_A")
    _add_claimed_seat(admin, student_a, "B", "JOIN_B")
    _add_claimed_seat(admin, student_b, "B", "JOIN_B")

    db.session.add_all(
        [
            Transaction(
                student_id=student_a.id,
                amount=10,
                type="bonus",
                account_type="checking",
                description="A-scoped",
                join_code="JOIN_A",
            ),
            Transaction(
                student_id=student_a.id,
                amount=25,
                type="bonus",
                account_type="checking",
                description="B-scoped",
                join_code="JOIN_B",
            ),
            Transaction(
                student_id=student_b.id,
                amount=15,
                type="bonus",
                account_type="checking",
                description="B-only",
                join_code="JOIN_B",
            ),
        ]
    )
    db.session.commit()

    _as_admin_session(client, admin)
    response = client.get("/admin/export-students?join_code=JOIN_A")

    assert response.status_code == 200
    rows = list(csv.reader(StringIO(response.get_data(as_text=True))))
    assert len(rows) == 2  # header + one scoped student row

    header, data_row = rows
    assert header[0] == "First Name"
    assert data_row[0] == "Alice"
    assert data_row[2] == "A"
    assert data_row[3] == "10.00"
    assert data_row[5] == "10.00"


def test_export_students_rejects_invalid_join_code_scope(client):
    admin = _create_admin("export-admin-invalid")
    _as_admin_session(client, admin)

    response = client.get("/admin/export-students?join_code=NOT_MINE")

    assert response.status_code == 403
