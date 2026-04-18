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


def test_rent_pay_route_is_not_direct_ledger_or_obligations_authority():
    source = inspect.getsource(student_routes.rent_pay)
    assert "Transaction(" not in source
    assert "RentPayment(" not in source
    assert "execute_rent_payment(" in source


def test_transfer_route_is_not_direct_ledger_authority():
    source = inspect.getsource(student_routes.transfer)
    assert "Transaction(" not in source
    assert "execute_account_transfer(" in source


def test_purchase_insurance_route_is_not_direct_ledger_or_obligations_authority():
    source = inspect.getsource(student_routes.purchase_insurance)
    assert "Transaction(" not in source
    assert "StudentInsurance(" not in source
    assert "execute_insurance_purchase(" in source


def test_admin_void_route_is_not_direct_ledger_authority():
    admin_source = Path("app/routes/admin.py").read_text()
    start = admin_source.index("def void_transaction(")
    end = admin_source.index("# -------------------- HALL PASS MANAGEMENT --------------------")
    source = admin_source[start:end]
    assert "Transaction(" not in source
    assert "create_idempotent_transaction(" not in source
    assert "execute_void_transaction(" in source


def test_store_purchase_route_is_not_direct_ledger_or_store_authority():
    api_source = Path("app/routes/api.py").read_text()
    purchase_source = inspect.getsource(__import__("app.routes.api", fromlist=["purchase_item"]).purchase_item)
    assert "Transaction(" not in purchase_source
    assert "StudentItem(" not in purchase_source
    assert "execute_store_purchase(" in purchase_source
    assert "execute_rent_perk_purchase(" in purchase_source
    assert "db.session.commit()" not in purchase_source


def test_feat_modules_do_not_construct_transactions_or_write_rows_directly():
    for path in [
        Path("app/feats/rent_payment_feat.py"),
        Path("app/feats/store_purchase_feat.py"),
        Path("app/feats/transfer_feat.py"),
        Path("app/feats/insurance_purchase_feat.py"),
        Path("app/feats/transaction_void_feat.py"),
    ]:
        source = path.read_text()
        assert "Transaction(" not in source
        assert "db.session.add(" not in source
        assert "StudentItem(" not in source
        assert "RentPayment(" not in source


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
