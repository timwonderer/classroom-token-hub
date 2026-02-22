from datetime import datetime, timezone, timedelta
from decimal import Decimal

from werkzeug.security import generate_password_hash

from app import db
from app.hash_utils import get_random_salt, hash_username
from app.models import (
    Admin,
    Student,
    StudentTeacher,
    TeacherBlock,
    RentSettings,
    RentItem,
    RentPayment,
    StoreItem,
    Transaction,
)
from app.routes.student import _calculate_rent_coverage_due_date


def test_overdue_rent_payment_restores_privileges(client):
    teacher = Admin(username="rent_teacher_overdue", totp_secret="secret123")
    db.session.add(teacher)
    db.session.commit()

    salt = get_random_salt()
    student = Student(
        first_name="Rent",
        last_initial="P",
        block="A",
        salt=salt,
        username_hash=hash_username("rent_student_overdue", salt),
        pin_hash=generate_password_hash("1234"),
    )
    db.session.add(student)
    db.session.commit()

    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher.id))
    db.session.commit()

    join_code = "JOINA"
    seat = TeacherBlock(
        teacher_id=teacher.id,
        block="A",
        first_name="Rent",
        last_initial="P",
        last_name_hash_by_part=["hash_a"],
        dob_sum=2025,
        salt=b"rent_salt",
        first_half_hash="hash_a",
        join_code=join_code,
        student_id=student.id,
        is_claimed=True,
    )
    db.session.add(seat)
    db.session.commit()

    now = datetime.now(timezone.utc)
    rent_settings = RentSettings(
        teacher_id=teacher.id,
        block="A",
        join_code=join_code,
        is_enabled=True,
        rent_amount=Decimal("50.00"),
        first_rent_due_date=now - timedelta(days=5),
        grace_period_days=3,
        bill_preview_enabled=True,
        bill_preview_days=10,
    )
    db.session.add(rent_settings)
    db.session.commit()

    store_item = StoreItem(
        teacher_id=teacher.id,
        join_code=join_code,
        name="Desk Privilege",
        description="Desk access",
        price=Decimal("5.00"),
        item_type="delayed",
        is_active=True,
    )
    db.session.add(store_item)
    db.session.commit()

    rent_item = RentItem(
        rent_setting_id=rent_settings.id,
        name="Desk Privilege",
        description="Desk access",
        rent_item_type="privilege",
        is_available_in_store=True,
        store_price=Decimal("5.00"),
        store_item_id=store_item.id,
        purchase_duration="per_period",
    )
    db.session.add(rent_item)
    db.session.commit()

    with client.session_transaction() as sess:
        sess["student_id"] = student.id
        sess["login_time"] = now.isoformat()
        sess["current_join_code"] = join_code

    response = client.get("/student/shop")
    assert response.status_code == 200
    assert b"Included in your rent!" not in response.data

    coverage_due_date = _calculate_rent_coverage_due_date(rent_settings, now)
    assert coverage_due_date is not None

    payment_date = now
    grace_for_coverage = coverage_due_date + timedelta(days=rent_settings.grace_period_days)
    late_fee_applies = now > grace_for_coverage
    required_amount = rent_settings.rent_amount + (rent_settings.late_fee if late_fee_applies else Decimal("0.00"))
    payment = RentPayment(
        student_id=student.id,
        period="A",
        join_code=join_code,
        amount_paid=required_amount,
        period_month=now.month,
        period_year=now.year,
        payment_date=payment_date,
        coverage_month=coverage_due_date.month,
        coverage_year=coverage_due_date.year,
        was_late=True,
        late_fee_charged=rent_settings.late_fee if late_fee_applies else Decimal("0.00"),
    )
    transaction = Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code=join_code,
        amount=-required_amount,
        account_type="checking",
        type="Rent Payment",
        description="Overdue rent payment",
        timestamp=payment_date,
    )
    db.session.add_all([payment, transaction])
    db.session.commit()

    response = client.get("/student/shop")
    assert response.status_code == 200
    assert b"Included in your rent!" in response.data


def test_voided_payment_does_not_restore_privileges(client):
    teacher = Admin(username="rent_teacher_voided", totp_secret="secret123")
    db.session.add(teacher)
    db.session.commit()

    salt = get_random_salt()
    student = Student(
        first_name="Void",
        last_initial="P",
        block="A",
        salt=salt,
        username_hash=hash_username("rent_student_voided", salt),
        pin_hash=generate_password_hash("1234"),
    )
    db.session.add(student)
    db.session.commit()

    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher.id))
    db.session.commit()

    join_code = "JOINV"
    seat = TeacherBlock(
        teacher_id=teacher.id,
        block="A",
        first_name="Void",
        last_initial="P",
        last_name_hash_by_part=["hash_a"],
        dob_sum=2025,
        salt=b"rent_salt",
        first_half_hash="hash_a",
        join_code=join_code,
        student_id=student.id,
        is_claimed=True,
    )
    db.session.add(seat)
    db.session.commit()

    now = datetime.now(timezone.utc)
    rent_settings = RentSettings(
        teacher_id=teacher.id,
        block="A",
        join_code=join_code,
        is_enabled=True,
        rent_amount=Decimal("50.00"),
        first_rent_due_date=now - timedelta(days=5),
        grace_period_days=3,
        bill_preview_enabled=True,
        bill_preview_days=10,
    )
    db.session.add(rent_settings)
    db.session.commit()

    store_item = StoreItem(
        teacher_id=teacher.id,
        join_code=join_code,
        name="Desk Privilege",
        description="Desk access",
        price=Decimal("5.00"),
        item_type="delayed",
        is_active=True,
    )
    db.session.add(store_item)
    db.session.commit()

    rent_item = RentItem(
        rent_setting_id=rent_settings.id,
        name="Desk Privilege",
        description="Desk access",
        rent_item_type="privilege",
        is_available_in_store=True,
        store_price=Decimal("5.00"),
        store_item_id=store_item.id,
        purchase_duration="per_period",
    )
    db.session.add(rent_item)
    db.session.commit()

    with client.session_transaction() as sess:
        sess["student_id"] = student.id
        sess["login_time"] = now.isoformat()
        sess["current_join_code"] = join_code

    coverage_due_date = _calculate_rent_coverage_due_date(rent_settings, now)
    assert coverage_due_date is not None

    payment_date = now
    grace_for_coverage = coverage_due_date + timedelta(days=rent_settings.grace_period_days)
    late_fee_applies = now > grace_for_coverage
    required_amount = rent_settings.rent_amount + (rent_settings.late_fee if late_fee_applies else Decimal("0.00"))

    payment = RentPayment(
        student_id=student.id,
        period="A",
        join_code=join_code,
        amount_paid=required_amount,
        period_month=now.month,
        period_year=now.year,
        payment_date=payment_date,
        coverage_month=coverage_due_date.month,
        coverage_year=coverage_due_date.year,
        was_late=True,
        late_fee_charged=rent_settings.late_fee if late_fee_applies else Decimal("0.00"),
    )
    voided_tx = Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code=join_code,
        amount=-required_amount,
        account_type="checking",
        type="Rent Payment",
        description="Voided rent payment",
        timestamp=payment_date,
        is_void=True,
    )
    db.session.add_all([payment, voided_tx])
    db.session.commit()

    response = client.get("/student/shop")
    assert response.status_code == 200
    assert b"Included in your rent!" not in response.data

    valid_tx = Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code=join_code,
        amount=-required_amount,
        account_type="checking",
        type="Rent Payment",
        description="Valid rent payment",
        timestamp=payment_date + timedelta(seconds=10),
    )
    valid_payment = RentPayment(
        student_id=student.id,
        period="A",
        join_code=join_code,
        amount_paid=required_amount,
        period_month=now.month,
        period_year=now.year,
        payment_date=payment_date + timedelta(seconds=10),
        coverage_month=coverage_due_date.month,
        coverage_year=coverage_due_date.year,
        was_late=True,
        late_fee_charged=rent_settings.late_fee if late_fee_applies else Decimal("0.00"),
    )
    db.session.add_all([valid_tx, valid_payment])
    db.session.commit()

    response = client.get("/student/shop")
    assert response.status_code == 200
    assert b"Included in your rent!" in response.data


def test_overdue_rent_payment_with_timestamp_drift_restores_privileges(client):
    """A modest transaction/payment timestamp drift should still count as valid payment."""
    teacher = Admin(username="rent_teacher_drift", totp_secret="secret123")
    db.session.add(teacher)
    db.session.commit()

    salt = get_random_salt()
    student = Student(
        first_name="Drift",
        last_initial="P",
        block="A",
        salt=salt,
        username_hash=hash_username("rent_student_drift", salt),
        pin_hash=generate_password_hash("1234"),
    )
    db.session.add(student)
    db.session.commit()

    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher.id))
    db.session.commit()

    join_code = "JOIND"
    db.session.add(TeacherBlock(
        teacher_id=teacher.id,
        block="A",
        first_name="Drift",
        last_initial="P",
        last_name_hash_by_part=["hash_a"],
        dob_sum=2025,
        salt=b"rent_salt",
        first_half_hash="hash_a",
        join_code=join_code,
        student_id=student.id,
        is_claimed=True,
    ))
    db.session.commit()

    now = datetime.now(timezone.utc)
    rent_settings = RentSettings(
        teacher_id=teacher.id,
        block="A",
        join_code=join_code,
        is_enabled=True,
        rent_amount=Decimal("50.00"),
        first_rent_due_date=now - timedelta(days=5),
        grace_period_days=3,
        bill_preview_enabled=True,
        bill_preview_days=10,
    )
    db.session.add(rent_settings)
    db.session.commit()

    store_item = StoreItem(
        teacher_id=teacher.id,
        join_code=join_code,
        name="Desk Privilege Drift",
        description="Desk access",
        price=Decimal("5.00"),
        item_type="delayed",
        is_active=True,
    )
    db.session.add(store_item)
    db.session.commit()

    db.session.add(RentItem(
        rent_setting_id=rent_settings.id,
        name="Desk Privilege Drift",
        description="Desk access",
        rent_item_type="privilege",
        is_available_in_store=True,
        store_price=Decimal("5.00"),
        store_item_id=store_item.id,
        purchase_duration="per_period",
    ))
    db.session.commit()

    with client.session_transaction() as sess:
        sess["student_id"] = student.id
        sess["login_time"] = now.isoformat()
        sess["current_join_code"] = join_code

    coverage_due_date = _calculate_rent_coverage_due_date(rent_settings, now)
    assert coverage_due_date is not None
    grace_for_coverage = coverage_due_date + timedelta(days=rent_settings.grace_period_days)
    late_fee_applies = now > grace_for_coverage
    required_amount = rent_settings.rent_amount + (rent_settings.late_fee if late_fee_applies else Decimal("0.00"))

    payment_date = now
    txn_timestamp = now + timedelta(seconds=45)  # outside old 5s window; inside new tolerance
    db.session.add(RentPayment(
        student_id=student.id,
        period="A",
        join_code=join_code,
        amount_paid=required_amount,
        period_month=now.month,
        period_year=now.year,
        payment_date=payment_date,
        coverage_month=coverage_due_date.month,
        coverage_year=coverage_due_date.year,
        was_late=True,
        late_fee_charged=rent_settings.late_fee if late_fee_applies else Decimal("0.00"),
    ))
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code=join_code,
        amount=-required_amount,
        account_type="checking",
        type="Rent Payment",
        description="Overdue rent payment drifted timestamp",
        timestamp=txn_timestamp,
    ))
    db.session.commit()

    response = client.get("/student/shop")
    assert response.status_code == 200
    assert b"Included in your rent!" in response.data
