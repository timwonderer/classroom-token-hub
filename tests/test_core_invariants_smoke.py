from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

from app import db
from app.hash_utils import get_random_salt, hash_username
from app.models import (
    Admin,
    InsuranceClaim,
    InsurancePolicy,
    RentPayment,
    RentSettings,
    StoreItem,
    Student,
    StudentInsurance,
    StudentTeacher,
    TapEvent,
    TeacherBlock,
    Transaction,
    TransactionStatus,
)


pytestmark = pytest.mark.critical


def _create_admin(username: str) -> Admin:
    admin = Admin(username=username, totp_secret="test-secret")
    db.session.add(admin)
    db.session.flush()
    return admin


def _create_student(first_name: str, block: str = "A") -> Student:
    salt = get_random_salt()
    student = Student(
        first_name=first_name,
        last_initial="T",
        block=block,
        salt=salt,
        username_hash=hash_username(first_name.lower(), salt),
        pin_hash="pin-hash",
        passphrase_hash=generate_password_hash("password"),
    )
    db.session.add(student)
    db.session.flush()
    return student


def _link_student_to_teacher(student: Student, admin: Admin, join_code: str, block: str = "A") -> None:
    db.session.add(StudentTeacher(student_id=student.id, admin_id=admin.id))
    db.session.add(
        TeacherBlock(
            teacher_id=admin.id,
            student_id=student.id,
            block=block,
            join_code=join_code,
            is_claimed=True,
            first_name=student.first_name,
            last_initial=student.last_initial,
            last_name_hash_by_part=[],
            dob_sum=0,
            salt=b"seat-salt",
            first_half_hash="seat-hash",
        )
    )


def _login_admin(client, admin_id: int) -> None:
    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = admin_id
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()


def _login_student(client, student_id: int, join_code: str) -> None:
    with client.session_transaction() as sess:
        sess["student_id"] = student_id
        sess["current_join_code"] = join_code
        sess["login_time"] = datetime.now(timezone.utc).isoformat()
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()


def test_tenant_isolation_attendance_history(client):
    admin_a = _create_admin("tenant-a")
    admin_b = _create_admin("tenant-b")
    student_a = _create_student("Alice")
    student_b = _create_student("Bob")
    _link_student_to_teacher(student_a, admin_a, "JOIN-A")
    _link_student_to_teacher(student_b, admin_b, "JOIN-B")
    db.session.commit()

    tap_a = TapEvent(
        student_id=student_a.id,
        period="A",
        status="active",
        timestamp=datetime.now(timezone.utc),
        join_code="JOIN-A",
    )
    tap_b = TapEvent(
        student_id=student_b.id,
        period="A",
        status="active",
        timestamp=datetime.now(timezone.utc),
        join_code="JOIN-B",
    )
    db.session.add_all([tap_a, tap_b])
    db.session.commit()

    _login_admin(client, admin_a.id)
    response = client.get("/api/attendance/history")

    assert response.status_code == 200
    payload = response.get_json()
    ids = {row["id"] for row in payload["records"]}
    assert tap_a.id in ids
    assert tap_b.id not in ids


def test_payroll_run_creates_payroll_transaction(client):
    admin = _create_admin("payroll-admin")
    student = _create_student("Payroll")
    _link_student_to_teacher(student, admin, "JOIN-PAY", block="A")
    db.session.commit()

    now = datetime.now(timezone.utc)
    db.session.add_all(
        [
            TapEvent(
                student_id=student.id,
                period="A",
                status="active",
                timestamp=now - timedelta(minutes=60),
                join_code="JOIN-PAY",
            ),
            TapEvent(
                student_id=student.id,
                period="A",
                status="inactive",
                timestamp=now - timedelta(minutes=30),
                join_code="JOIN-PAY",
            ),
        ]
    )
    db.session.add(
        Transaction(
            student_id=student.id,
            teacher_id=admin.id,
            join_code="JOIN-PAY",
            amount=Decimal("1.00"),
            account_type="checking",
            status=TransactionStatus.POSTED,
            type="payroll",
            description="Anchor payroll",
            timestamp=now - timedelta(days=1),
        )
    )
    db.session.commit()

    _login_admin(client, admin.id)
    response = client.post("/admin/run-payroll", json={})

    assert response.status_code == 200
    tx = Transaction.query.filter_by(
        student_id=student.id,
        teacher_id=admin.id,
        join_code="JOIN-PAY",
        type="payroll",
    ).first()
    assert tx is not None
    assert tx.amount > Decimal("0.00")


def test_insurance_approval_creates_reimbursement_transaction(client):
    admin = _create_admin("insurance-admin")
    student = _create_student("Insured")
    _link_student_to_teacher(student, admin, "JOIN-INS", block="A")
    db.session.commit()

    policy = InsurancePolicy(
        policy_code=f"POL-{admin.id}",
        teacher_id=admin.id,
        title="Coverage",
        description="Test policy",
        premium=Decimal("10.00"),
        claim_type="transaction_monetary",
        is_monetary=True,
        max_claim_amount=Decimal("100.00"),
        max_claims_period="month",
        claim_time_limit_days=30,
        is_active=True,
    )
    db.session.add(policy)
    db.session.flush()

    enrollment = StudentInsurance(
        student_id=student.id,
        policy_id=policy.id,
        status="active",
        join_code="JOIN-INS",
        purchase_date=datetime.now(timezone.utc),
        coverage_start_date=datetime.now(timezone.utc) - timedelta(days=1),
        payment_current=True,
    )
    enrollment.freeze_policy_snapshot(policy)
    db.session.add(enrollment)
    db.session.flush()

    purchase_tx = Transaction(
        student_id=student.id,
        teacher_id=admin.id,
        join_code="JOIN-INS",
        amount=Decimal("-30.00"),
        account_type="checking",
        status=TransactionStatus.POSTED,
        type="purchase",
        description="Purchase: broken item",
    )
    db.session.add(purchase_tx)
    db.session.flush()

    claim = InsuranceClaim(
        student_insurance_id=enrollment.id,
        policy_id=policy.id,
        student_id=student.id,
        incident_date=purchase_tx.timestamp,
        description="Reimburse",
        claim_amount=Decimal("30.00"),
        status="pending",
        transaction_id=purchase_tx.id,
    )
    db.session.add(claim)
    db.session.commit()

    _login_admin(client, admin.id)
    response = client.post(
        f"/admin/insurance/claim/{claim.id}",
        data={"status": "approved", "approved_amount": "", "rejection_reason": "", "admin_notes": ""},
        follow_redirects=True,
    )

    assert response.status_code == 200
    reimbursement = Transaction.query.filter_by(
        type="insurance_reimbursement",
        original_transaction_id=purchase_tx.id,
        policy_id=policy.id,
    ).first()
    assert reimbursement is not None
    assert reimbursement.amount > Decimal("0.00")


def test_store_purchase_deducts_balance_and_records_transaction(client):
    admin = _create_admin("store-admin")
    student = _create_student("Shopper")
    _link_student_to_teacher(student, admin, "JOIN-STORE", block="A")
    db.session.commit()

    item = StoreItem(
        teacher_id=admin.id,
        name="Notebook",
        price=Decimal("5.00"),
        is_active=True,
        item_type="delayed",
    )
    db.session.add(item)
    db.session.add(
        Transaction(
            student_id=student.id,
            teacher_id=admin.id,
            join_code="JOIN-STORE",
            amount=Decimal("25.00"),
            account_type="checking",
            status=TransactionStatus.POSTED,
            type="Deposit",
            description="Seed funds",
        )
    )
    db.session.commit()

    starting_balance = student.get_checking_balance(teacher_id=admin.id, join_code="JOIN-STORE")

    _login_student(client, student.id, "JOIN-STORE")
    response = client.post(
        "/api/purchase-item",
        json={"item_id": item.id, "passphrase": "password", "quantity": 1},
    )

    assert response.status_code == 200
    ending_balance = student.get_checking_balance(teacher_id=admin.id, join_code="JOIN-STORE")
    assert ending_balance < starting_balance

    purchase_tx = (
        Transaction.query.filter_by(
            student_id=student.id,
            teacher_id=admin.id,
            join_code="JOIN-STORE",
            type="purchase",
        )
        .order_by(Transaction.id.desc())
        .first()
    )
    assert purchase_tx is not None
    assert purchase_tx.amount < Decimal("0.00")


def test_rent_payment_creates_rent_obligation_record(client):
    admin = _create_admin("rent-admin")
    student = _create_student("Renter")
    _link_student_to_teacher(student, admin, "JOIN-RENT", block="A")

    settings = RentSettings(
        teacher_id=admin.id,
        block="A",
        is_enabled=True,
        rent_amount=Decimal("10.00"),
        frequency_type="monthly",
        due_day_of_month=1,
        grace_period_days=0,
        late_penalty_amount=Decimal("0.00"),
    )
    db.session.add(settings)
    db.session.add(
        Transaction(
            student_id=student.id,
            teacher_id=admin.id,
            join_code="JOIN-RENT",
            amount=Decimal("40.00"),
            account_type="checking",
            status=TransactionStatus.POSTED,
            type="Deposit",
            description="Seed funds",
        )
    )
    db.session.commit()

    _login_student(client, student.id, "JOIN-RENT")
    response = client.post("/student/rent/pay/A", follow_redirects=False)
    assert response.status_code in (302, 303)

    rent_payment = RentPayment.query.filter_by(student_id=student.id, join_code="JOIN-RENT").first()
    assert rent_payment is not None

    rent_tx = (
        Transaction.query.filter_by(
            student_id=student.id,
            teacher_id=admin.id,
            join_code="JOIN-RENT",
            type="Rent Payment",
        )
        .order_by(Transaction.id.desc())
        .first()
    )
    assert rent_tx is not None
