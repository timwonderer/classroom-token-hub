with open("tests/test_idempotency.py", "w") as f:
    f.write("""
import pytest
from app.models import LedgerTransaction, Seat, Class, User
from app.extensions import db
from sqlalchemy.exc import IntegrityError
import uuid

def test_idempotency_key_enforcement(app):
    with app.app_context():
        user = User(username_lookup_hash=str(uuid.uuid4()), passphrase_hash="hash", user_role="STUDENT")
        db.session.add(user)
        db.session.commit()

        cls = Class(join_code=str(uuid.uuid4())[:20], class_timezone="UTC")
        db.session.add(cls)
        db.session.commit()

        seat = Seat(user_id=user.id, class_id=cls.class_id, role="STUDENT")
        db.session.add(seat)
        db.session.commit()

        tx1 = LedgerTransaction(
            seat_id=seat.id,
            amount_cents=100,
            status="POSTED",
            category="SYSTEM",
            correlation_id="corr-1",
            idempotency_key="idem-key-1"
        )
        db.session.add(tx1)
        db.session.commit()

        tx2 = LedgerTransaction(
            seat_id=seat.id,
            amount_cents=200,
            status="POSTED",
            category="SYSTEM",
            correlation_id="corr-2",
            idempotency_key="idem-key-1"
        )
        db.session.add(tx2)
        try:
            db.session.commit()
            pytest.fail("Should have raised IntegrityError")
        except Exception as e:
            db.session.rollback()
            assert isinstance(e, IntegrityError) or "IntegrityError" in type(e).__name__
""")

with open("tests/test_append_only.py", "w") as f:
    f.write("""
import pytest
from app.models import LedgerTransaction, Seat, Class, User
from app.extensions import db
from sqlalchemy.exc import InternalError, ProgrammingError, StatementError, OperationalError, DataError, DatabaseError
import uuid

def test_append_only_enforcement(app):
    with app.app_context():
        user = User(username_lookup_hash=str(uuid.uuid4()), passphrase_hash="hash", user_role="STUDENT")
        db.session.add(user)
        db.session.commit()

        cls = Class(join_code=str(uuid.uuid4())[:20], class_timezone="UTC")
        db.session.add(cls)
        db.session.commit()

        seat = Seat(user_id=user.id, class_id=cls.class_id, role="STUDENT")
        db.session.add(seat)
        db.session.commit()

        tx1 = LedgerTransaction(
            seat_id=seat.id,
            amount_cents=100,
            status="POSTED",
            category="SYSTEM",
            correlation_id="corr-1",
            idempotency_key="idem-key-1"
        )
        db.session.add(tx1)
        db.session.commit()

        tx1.status = "VOID"
        try:
            db.session.commit()
            pytest.fail("Should have raised an error on update")
        except (InternalError, ProgrammingError, StatementError, OperationalError, DataError, DatabaseError) as e:
            db.session.rollback()
            assert "Updates and Deletes are prohibited" in str(e)
""")
