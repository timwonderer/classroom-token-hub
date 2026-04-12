from datetime import datetime, timezone
from decimal import Decimal

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app.extensions import db
from app.models import Admin, Student, StudentTeacher, TeacherBlock, Transaction, TransactionStatus
from tests.helpers.class_scope import create_class_scope


def _login_admin(client, admin_id):
    with client.session_transaction() as sess:
        sess["admin_id"] = admin_id
        sess["is_admin"] = True
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()


def test_admin_payroll_displays_scoped_balances_only(client):
    teacher_a = make_admin("payroll_scope_a", "secret-a")
    teacher_b = make_admin("payroll_scope_b", "secret-b")
    db.session.add_all([teacher_a, teacher_b])
    db.session.flush()

    student = Student(first_name="Pay", last_initial="S", block="A", salt=b"salt")
    db.session.add(student)
    db.session.flush()

    class_a = create_class_scope(teacher=teacher_a, join_code="PAYA01", student=student, block="A", display_name="A")
    class_b = create_class_scope(teacher=teacher_b, join_code="PAYB01", student=student, block="A", display_name="A")
    db.session.flush()

    db.session.add_all([
        StudentTeacher(student_id=student.id, teacher_id=teacher_a.id),
        StudentTeacher(student_id=student.id, teacher_id=teacher_b.id),
        TeacherBlock(
            teacher_id=teacher_a.id,
            block="A",
            join_code="PAYA01",
            class_id=class_a.class_id,
            student_id=student.id,
            is_claimed=True,
            first_name=student.first_name,
            last_initial=student.last_initial,
            last_name_hash_by_part=[],
            dob_sum_hash=None,
            salt=b"salt",
            first_half_hash="hash-a",
        ),
        TeacherBlock(
            teacher_id=teacher_b.id,
            block="A",
            join_code="PAYB01",
            class_id=class_b.class_id,
            student_id=student.id,
            is_claimed=True,
            first_name=student.first_name,
            last_initial=student.last_initial,
            last_name_hash_by_part=[],
            dob_sum_hash=None,
            salt=b"salt",
            first_half_hash="hash-b",
        ),
        Transaction(
            student_id=student.id,
            teacher_id=teacher_a.id,
            join_code="PAYA01",
            amount=Decimal("111.11"),
            account_type="checking",
            status=TransactionStatus.PENDING,
            type="deposit",
            description="Teacher A balance",
        ),
        Transaction(
            student_id=student.id,
            teacher_id=teacher_b.id,
            join_code="PAYB01",
            amount=Decimal("222.22"),
            account_type="checking",
            status=TransactionStatus.PENDING,
            type="deposit",
            description="Teacher B balance",
        ),
    ])
    db.session.commit()

    _login_admin(client, teacher_a.id)
    response = client.get("/admin/payroll")
    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "$111.11" in body
    assert "$222.22" not in body
