import os
print("Rebuilding Test Suite")

with open("tests/test_idempotency.py", "w") as f:
    f.write("""
import pytest
from app.models import LedgerTransaction
from app.extensions import db
from sqlalchemy.exc import IntegrityError

def test_idempotency_key_enforcement(app):
    with app.app_context():
        tx1 = LedgerTransaction(
            seat_id=1,
            amount_cents=100,
            status="POSTED",
            category="SYSTEM",
            correlation_id="corr-1",
            idempotency_key="idem-key-1"
        )
        db.session.add(tx1)
        db.session.commit()

        tx2 = LedgerTransaction(
            seat_id=1,
            amount_cents=200,
            status="POSTED",
            category="SYSTEM",
            correlation_id="corr-2",
            idempotency_key="idem-key-1"
        )
        db.session.add(tx2)
        with pytest.raises(IntegrityError):
            db.session.commit()
""")

with open("tests/test_append_only.py", "w") as f:
    f.write("""
import pytest
from app.models import LedgerTransaction
from app.extensions import db
from sqlalchemy.exc import InternalError

def test_append_only_enforcement(app):
    with app.app_context():
        tx1 = LedgerTransaction(
            seat_id=1,
            amount_cents=100,
            status="POSTED",
            category="SYSTEM",
            correlation_id="corr-1",
            idempotency_key="idem-key-1"
        )
        db.session.add(tx1)
        db.session.commit()

        tx1.status = "VOID"
        with pytest.raises(InternalError) as excinfo:
            db.session.commit()
        assert "Updates and Deletes are prohibited" in str(excinfo.value)
""")

with open("tests/test_class_scoping.py", "w") as f:
    f.write("""
import pytest
from app.models import Seat, Class
from app.extensions import db
from sqlalchemy.exc import IntegrityError

def test_class_scoping_enforcement(app):
    with app.app_context():
        # Ensure class_id is required
        seat = Seat(role="STUDENT", public_id="pub-1")
        db.session.add(seat)
        with pytest.raises(IntegrityError):
            db.session.commit()
""")
