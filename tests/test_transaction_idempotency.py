from decimal import Decimal

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Admin, Student, Transaction
import app.utils.transaction_idempotency as transaction_idempotency
from app.utils.transaction_idempotency import (
    IDEMPOTENT_TRANSACTION_TYPES,
    MAX_IDEMPOTENCY_KEY_LENGTH,
    create_idempotent_transaction,
    insurance_reimbursement_key,
)


def test_idempotent_transaction_types_are_explicit():
    assert IDEMPOTENT_TRANSACTION_TYPES == frozenset({"insurance_reimbursement", "purchase", "refund"})


def test_create_idempotent_transaction_reuses_existing_row_on_retry(client):
    teacher = make_admin("idempotent-teacher", "secret")
    student = Student(first_name="Retry", last_initial="R", block="A", salt=b"salt")
    db.session.add_all([teacher, student])
    db.session.commit()

    idempotency_key = insurance_reimbursement_key(123)
    transaction_one, created_one = create_idempotent_transaction(
        idempotency_key=idempotency_key,
        student_id=student.id,
        teacher_id=teacher.id,
        join_code="IDEMP123",
        amount=Decimal("10.00"),
        account_type="checking",
        type="insurance_reimbursement",
        description="Insurance reimbursement",
    )
    transaction_two, created_two = create_idempotent_transaction(
        idempotency_key=idempotency_key,
        student_id=student.id,
        teacher_id=teacher.id,
        join_code="IDEMP123",
        amount=Decimal("10.00"),
        account_type="checking",
        type="insurance_reimbursement",
        description="Insurance reimbursement",
    )

    assert created_one is True
    assert created_two is False
    assert transaction_one.id == transaction_two.id
    assert Transaction.query.filter_by(idempotency_key=idempotency_key).count() == 1


def test_create_idempotent_transaction_recovers_from_integrity_race(client, monkeypatch):
    teacher = make_admin("idempotent-race-teacher", "secret")
    student = Student(first_name="Race", last_initial="R", block="A", salt=b"salt")
    db.session.add_all([teacher, student])
    db.session.commit()

    idempotency_key = insurance_reimbursement_key(456)
    winning_tx = Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code="IDEMP456",
        amount=Decimal("11.00"),
        account_type="checking",
        type="insurance_reimbursement",
        description="Winning insurance reimbursement",
        idempotency_key=idempotency_key,
    )
    db.session.add(winning_tx)
    db.session.commit()

    lookup_calls = {"count": 0}

    def racing_lookup(key):
        lookup_calls["count"] += 1
        if lookup_calls["count"] == 1:
            return None
        return Transaction.query.filter_by(idempotency_key=key).one_or_none()

    def racing_flush(*args, **kwargs):
        raise IntegrityError("duplicate key", params=None, orig=Exception("duplicate key"))

    monkeypatch.setattr(transaction_idempotency, "get_idempotent_transaction", racing_lookup)
    monkeypatch.setattr(db.session, "flush", racing_flush)

    transaction, created = create_idempotent_transaction(
        idempotency_key=idempotency_key,
        student_id=student.id,
        teacher_id=teacher.id,
        join_code="IDEMP456",
        amount=Decimal("11.00"),
        account_type="checking",
        type="insurance_reimbursement",
        description="Losing insurance reimbursement",
    )

    assert created is False
    assert transaction is not None
    assert transaction.id == winning_tx.id
    assert transaction.idempotency_key == idempotency_key
    assert Transaction.query.filter_by(idempotency_key=idempotency_key).count() == 1


def test_create_idempotent_transaction_rejects_non_idempotent_types(client):
    teacher = make_admin("idempotent-invalid-teacher", "secret")
    student = Student(first_name="Nope", last_initial="N", block="A", salt=b"salt")
    db.session.add_all([teacher, student])
    db.session.commit()

    with pytest.raises(ValueError):
        create_idempotent_transaction(
            idempotency_key="txn:payroll:block:a",
            student_id=student.id,
            teacher_id=teacher.id,
            join_code="IDEMP789",
            amount=Decimal("5.00"),
            account_type="checking",
            type="payroll",
            description="Should fail",
        )


@pytest.mark.parametrize("bad_key", [None, "", "   "])
def test_create_idempotent_transaction_rejects_empty_keys(client, bad_key):
    teacher = make_admin("idempotent-empty-key-teacher", "secret")
    student = Student(first_name="Empty", last_initial="E", block="A", salt=b"salt")
    db.session.add_all([teacher, student])
    db.session.commit()

    with pytest.raises(ValueError):
        create_idempotent_transaction(
            idempotency_key=bad_key,
            student_id=student.id,
            teacher_id=teacher.id,
            join_code="IDEMP000",
            amount=Decimal("5.00"),
            account_type="checking",
            type="refund",
            description="Should fail",
        )


def test_create_idempotent_transaction_rejects_oversize_keys(client):
    teacher = make_admin("idempotent-long-key-teacher", "secret")
    student = Student(first_name="Long", last_initial="L", block="A", salt=b"salt")
    db.session.add_all([teacher, student])
    db.session.commit()

    with pytest.raises(ValueError):
        create_idempotent_transaction(
            idempotency_key="x" * (MAX_IDEMPOTENCY_KEY_LENGTH + 1),
            student_id=student.id,
            teacher_id=teacher.id,
            join_code="IDEMP001",
            amount=Decimal("5.00"),
            account_type="checking",
            type="refund",
            description="Should fail",
        )
