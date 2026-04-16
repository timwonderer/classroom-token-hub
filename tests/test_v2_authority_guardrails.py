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


# ---------------------------------------------------------------------------
# Wave2 guardrails (item 8)
# ---------------------------------------------------------------------------

def test_rent_pay_route_does_not_create_transaction_directly():
    """rent_pay must delegate all writes to rent_payment_feat.execute_rent_payment."""
    source = inspect.getsource(student_routes.rent_pay)
    assert "Transaction(" not in source, (
        "rent_pay() creates Transaction() directly. Route must delegate to "
        "rent_payment_feat.execute_rent_payment()."
    )


def test_student_transfer_route_does_not_create_transaction_directly():
    """transfer route must use ledger_service.create_transfer_pair, not Transaction()."""
    source = inspect.getsource(student_routes.transfer)
    assert "Transaction(" not in source, (
        "transfer() creates Transaction() directly. Use ledger_service.create_transfer_pair()."
    )


def test_student_purchase_insurance_does_not_create_transaction_directly():
    """Insurance purchase must use ledger_service, not Transaction()."""
    source = inspect.getsource(student_routes.purchase_insurance)
    assert "Transaction(" not in source, (
        "purchase_insurance() creates Transaction() directly. Use ledger_service."
    )


def test_attendance_module_is_zero_logic():
    """
    attendance.py must be a pure compatibility shim – every public function
    must be a single-line delegation.  No raw DB queries, no local variables
    beyond what is needed to forward arguments, no conditional logic beyond
    what is required to compose function arguments.

    We verify this by checking the source does NOT contain model queries,
    sqlalchemy func calls, or business logic constructs.
    """
    source = Path("app/attendance.py").read_text()
    forbidden = [
        "TapEvent.query",
        "StudentBlock.query",
        "db.session.add(",
        "db.session.commit(",
        "func.date(",
        "func.max(",
    ]
    for pattern in forbidden:
        assert pattern not in source, (
            f"attendance.py contains '{pattern}' – it must be a zero-logic shim. "
            f"Move the implementation to attendance_service.py."
        )


def test_feats_directory_exists_with_required_feats():
    """Wave2 FEATs must exist and be importable."""
    from app.feats import rent_payment_feat, store_purchase_feat  # noqa: F401
    assert callable(rent_payment_feat.execute_rent_payment)
    assert callable(store_purchase_feat.execute_store_purchase)


def test_rent_payment_feat_creates_transaction_via_ledger_service():
    """rent_payment_feat must not call Transaction() directly."""
    source = Path("app/feats/rent_payment_feat.py").read_text()
    assert "Transaction(" not in source, (
        "rent_payment_feat creates Transaction() directly. Use ledger_service.create_pending_transaction()."
    )


def test_store_purchase_feat_creates_transaction_via_ledger_service():
    """store_purchase_feat must not call Transaction() directly."""
    source = Path("app/feats/store_purchase_feat.py").read_text()
    assert "Transaction(" not in source, (
        "store_purchase_feat creates Transaction() directly. Use ledger_service.create_pending_transaction()."
    )

