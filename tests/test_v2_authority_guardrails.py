from datetime import datetime, timedelta, timezone
import inspect
from pathlib import Path

from app.extensions import db
from app.models import Student, StudentTeacher, Transaction
from app.routes import student as student_routes
from app.services import attendance_service
from tests.helpers.class_scope import create_class_scope
from tests.helpers.v2_fixtures import make_admin


def _login_student(client, student_id, join_code):
    with client.session_transaction() as sess:
        sess["student_id"] = student_id
        sess["current_join_code"] = join_code
        sess["login_time"] = datetime.now(timezone.utc).isoformat()


def test_student_dashboard_does_not_trigger_hidden_mutation_calls():
    source = inspect.getsource(student_routes.dashboard)
    assert "apply_savings_interest(" not in source
    assert "_ensure_rent_hall_pass_top_off(" not in source


def test_student_shop_does_not_trigger_collective_goal_reconciliation():
    source = inspect.getsource(student_routes.shop)
    assert "process_expired_collective_goals(" not in source


def test_route_modules_do_not_use_legacy_balance_properties():
    route_sources = {
        path.name: path.read_text()
        for path in [
            Path("app/routes/student.py"),
            Path("app/routes/api.py"),
            Path("app/routes/admin.py"),
        ]
    }
    for name, source in route_sources.items():
        assert ".checking_balance" not in source, f"{name} still uses model-level checking balance authority"
        assert ".savings_balance" not in source, f"{name} still uses model-level savings balance authority"


def test_attendance_service_does_not_compute_pay_or_pull_internal_payroll_anchors():
    source = inspect.getsource(attendance_service)
    assert "get_pay_rate_for_block" not in source
    assert "get_last_payroll_time(" not in source


def test_dashboard_read_is_interest_mutation_free(client):
    teacher = make_admin("dash_guard_teacher", "secret")
    db.session.add(teacher)
    db.session.flush()

    student = Student(first_name="Read", last_initial="P", block="A", salt=b"salt", has_completed_setup=True)
    db.session.add(student)
    db.session.flush()

    join_code = "READPURE1"
    create_class_scope(
        teacher=teacher,
        join_code=join_code,
        student=student,
        block="A",
        display_name="A",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
    )
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    mature_savings_time = datetime.now(timezone.utc) - timedelta(days=31)
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code=join_code,
        amount=100.0,
        account_type="savings",
        description="Savings Seed",
        timestamp=mature_savings_time,
        date_funds_available=mature_savings_time,
    ))
    db.session.commit()

    before_count = Transaction.query.filter_by(student_id=student.id).count()
    _login_student(client, student.id, join_code)

    response = client.get("/student/dashboard")

    assert response.status_code == 200
    after_count = Transaction.query.filter_by(student_id=student.id).count()
    assert after_count == before_count
    assert Transaction.query.filter_by(
        student_id=student.id,
        description="Monthly Savings Interest",
        account_type="savings",
    ).first() is None
