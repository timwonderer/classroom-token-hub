from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.models import Admin, ClassEconomy, ClassMembership, Student, StudentTeacher, TeacherBlock, Transaction, TransactionStatus


def _login_admin(client, admin_id):
    with client.session_transaction() as sess:
        sess["admin_id"] = admin_id
        sess["is_admin"] = True
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()


def test_admin_payroll_displays_scoped_balances_only(client):
    teacher_a = Admin(username="payroll_scope_a", totp_secret="secret-a")
    teacher_b = Admin(username="payroll_scope_b", totp_secret="secret-b")
    db.session.add_all([teacher_a, teacher_b])
    db.session.flush()

    student = Student(first_name="Pay", last_initial="S", block="A", salt=b"salt")
    db.session.add(student)
    db.session.flush()

    db.session.add_all([
        StudentTeacher(student_id=student.id, teacher_id=teacher_a.id),
        StudentTeacher(student_id=student.id, teacher_id=teacher_b.id),
        ClassEconomy(join_code="PAYA01", status="active", created_by_admin_id=teacher_a.id),
        ClassEconomy(join_code="PAYB01", status="active", created_by_admin_id=teacher_b.id),
        ClassMembership(join_code="PAYA01", admin_id=teacher_a.id, role="admin", status="active"),
        ClassMembership(join_code="PAYB01", admin_id=teacher_b.id, role="admin", status="active"),
        ClassMembership(join_code="PAYA01", student_id=student.id, role="student", status="active"),
        ClassMembership(join_code="PAYB01", student_id=student.id, role="student", status="active"),
        TeacherBlock(
            teacher_id=teacher_a.id,
            block="A",
            join_code="PAYA01",
            student_id=student.id,
            is_claimed=True,
            first_name=student.first_name,
            last_initial=student.last_initial,
            last_name_hash_by_part=[],
            dob_sum=0,
            salt=b"salt",
            first_half_hash="hash-a",
        ),
        TeacherBlock(
            teacher_id=teacher_b.id,
            block="A",
            join_code="PAYB01",
            student_id=student.id,
            is_claimed=True,
            first_name=student.first_name,
            last_initial=student.last_initial,
            last_name_hash_by_part=[],
            dob_sum=0,
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
