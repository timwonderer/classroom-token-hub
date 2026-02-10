import pytest
from decimal import Decimal
from app.extensions import db
from app.models import Transaction, Admin, Student, StudentItem, StoreItem, SystemAdmin
from app.services.reversal_service import ReversalService, ReversalError, NonReversibleError, ValidationFailureError
from app.hash_utils import get_random_salt

class TestReversalService:

    @pytest.fixture(autouse=True)
    def setup_data(self, client):
        self.salt = get_random_salt()
        self.teacher = Admin(username="teacher", totp_secret="secret", salt=self.salt)
        self.sysadmin = SystemAdmin(username="sysadmin", totp_secret="secret")
        self.student = Student(
            first_name="Test",
            last_initial="S",
            block="A",
            salt=self.salt
        )
        db.session.add(self.teacher)
        db.session.add(self.sysadmin)
        db.session.add(self.student)
        db.session.commit()

        self.join_code = "TEST1234"

    def create_transaction(self, amount, tx_type, description="test", account="checking"):
        tx = Transaction(
            student_id=self.student.id,
            teacher_id=self.teacher.id,
            join_code=self.join_code,
            amount=Decimal(amount),
            type=tx_type,
            description=description,
            account_type=account
        )
        db.session.add(tx)
        db.session.commit()
        return tx

    def test_reversal_happy_path(self):
        """Test standard reversal of a reversible transaction."""
        original = self.create_transaction("100.00", "manual_bonus", "Good work")

        counter = ReversalService.reverse_transaction(
            transaction_id=original.id,
            actor=self.teacher,
            reason="Mistake"
        )

        assert counter is not None
        assert counter.amount == Decimal("-100.00")
        assert counter.original_transaction_id == original.id
        assert counter.type.startswith("Reversal:")
        assert "Mistake" in counter.description

        # Verify ledger sum is zero
        total = original.amount + counter.amount
        assert total == 0

    def test_idempotency(self):
        """Verify duplicate reversals return existing counter-tx without error."""
        original = self.create_transaction("50.00", "manual_fine", "Bad work")

        tx1 = ReversalService.reverse_transaction(original.id, self.teacher, "Undo 1")
        tx2 = ReversalService.reverse_transaction(original.id, self.teacher, "Undo 2")

        assert tx1.id == tx2.id
        assert Transaction.query.filter_by(original_transaction_id=original.id).count() == 1

    def test_non_reversible_type(self):
        """Verify errors raised for non-reversible types."""
        # Transfer is marked False in map
        tx = self.create_transaction("50.00", "transfer", "Savings to Checking")

        with pytest.raises(NonReversibleError):
            ReversalService.reverse_transaction(tx.id, self.teacher, "Undo transfer")

    def test_store_purchase_reversal_state_update(self):
        """Verify reversing a store purchase updates the StudentItem status."""
        # 1. Create Store Item
        item = StoreItem(
            teacher_id=self.teacher.id,
            name="Pencil",
            price=Decimal("10.00"),
            item_type="physical",
            inventory=10
        )
        db.session.add(item)
        db.session.commit()

        # 2. Create Transaction (purchase)
        tx = self.create_transaction("-10.00", "store_purchase", "Bought Pencil")

        # 3. Create StudentItem (linked by time/student)
        student_item = StudentItem(
            student_id=self.student.id,
            store_item_id=item.id,
            join_code=self.join_code,
            status="purchased",
            purchase_date=tx.timestamp
        )
        db.session.add(student_item)
        db.session.commit()

        # 4. Reverse with ticket ID
        ReversalService.reverse_transaction(tx.id, self.teacher, "Refund", ticket_id=123)

        # 5. Check item status
        updated_item = db.session.get(StudentItem, student_item.id)
        assert updated_item.status == "refunded"

    def test_transaction_not_found(self):
        with pytest.raises(ReversalError) as excinfo:
            ReversalService.reverse_transaction(99999, self.teacher, "test")
        assert "not found" in str(excinfo.value)

    def test_ledger_integrity_after_reversal(self):
        """Ensure balance calculations respect the counter transaction."""
        tx1 = self.create_transaction("100.00", "manual_bonus")

        # Verify balance before
        bal1 = sum(t.amount for t in Transaction.query.filter_by(student_id=self.student.id).all())
        assert bal1 == Decimal("100.00")

        # Reverse
        ReversalService.reverse_transaction(tx1.id, self.teacher, "oops")

        # Verify balance after (Should be 0)
        bal2 = sum(t.amount for t in Transaction.query.filter_by(student_id=self.student.id).all())
        assert bal2 == Decimal("0.00")

        # Verify original is NOT voided (historical record preserved)
        refreshed_tx1 = db.session.get(Transaction, tx1.id)
        assert refreshed_tx1.is_void is False

    def test_conditional_validation_payroll_missing_ticket(self):
        """Test payroll reversal fails without ticket ID for Teacher."""
        tx = self.create_transaction("500.00", "payroll", "Weekly Pay")

        with pytest.raises(ValidationFailureError):
            ReversalService.reverse_transaction(tx.id, self.teacher, "Error fix")

    def test_conditional_validation_payroll_sysadmin_override(self):
        """Test payroll reversal allows Sysadmin without ticket ID."""
        tx = self.create_transaction("500.00", "payroll", "Weekly Pay")

        # Should NOT raise error
        ReversalService.reverse_transaction(tx.id, self.sysadmin, "System Fix")

    def test_conditional_validation_rent_late_fee_missing_ticket(self):
        """Test rent late fee reversal fails without ticket ID."""
        tx = self.create_transaction("-10.00", "rent_late_fee", "Late Fee")

        with pytest.raises(ValidationFailureError):
            ReversalService.reverse_transaction(tx.id, self.teacher, "Forgive")

    def test_conditional_validation_store_missing_ticket(self):
        """Test store purchase reversal fails without ticket ID."""
        tx = self.create_transaction("-5.00", "store_purchase", "Pencil")

        with pytest.raises(ValidationFailureError):
            ReversalService.reverse_transaction(tx.id, self.teacher, "Return")
