
import pytest
from app import create_app, db
from app.models import (
    Admin, Student, ClassEconomy, ClassMembership, TeacherBlock,
    RentSettings, StoreItem, Transaction, StudentItem
)
from werkzeug.security import generate_password_hash
from decimal import Decimal
import datetime

@pytest.fixture
def app():
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False
    })
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def db_session(app):
    with app.app_context():
        db.create_all()
        yield db.session
        db.session.remove()
        db.drop_all()

def test_phase_a_blockers(client, db_session, app):
    # Setup Data
    # 1. Teacher
    teacher = Admin(username="teacher1", totp_secret="secret")
    db_session.add(teacher)
    db_session.flush()

    # 2. Class Economy
    join_code = "JOIN123"
    economy = ClassEconomy(join_code=join_code, display_name="Math 101")
    db_session.add(economy)
    db_session.flush()

    # 3. Class Membership (Teacher)
    teacher_membership = ClassMembership(
        join_code=join_code,
        admin_id=teacher.id,
        role='admin',
        status='active'
    )
    db_session.add(teacher_membership)
    db_session.flush()

    # 4. Student
    student = Student(
        first_name="TestStudent",
        last_initial="T",
        block="A",
        salt=b'salt',
        pin_hash=generate_password_hash('1234'),
        passphrase_hash=generate_password_hash('pass')
    )
    db_session.add(student)
    db_session.flush()

    # 5. Class Membership (Student)
    student_membership = ClassMembership(
        join_code=join_code,
        student_id=student.id,
        role='student',
        status='active'
    )
    db_session.add(student_membership)
    db_session.flush()

    # 6. Teacher Block (Legacy Artifact for Display)
    teacher_block = TeacherBlock(
        teacher_id=teacher.id,
        block="A",
        first_name=b"TestStudent",
        last_initial="T",
        last_name_hash_by_part=[],
        dob_sum=100,
        salt=b'salt',
        first_half_hash="hash",
        join_code=join_code,
        student_id=student.id,
        is_claimed=True
    )
    db_session.add(teacher_block)

    # 7. Rent Settings
    rent_settings = RentSettings(
        teacher_id=teacher.id,
        block="A",
        join_code=join_code,
        rent_amount=Decimal('50.00'),
        is_enabled=True
    )
    db_session.add(rent_settings)

    # 8. Store Item (Owned by Teacher)
    store_item = StoreItem(
        teacher_id=teacher.id,
        name="Pencil",
        price=Decimal('10.00'),
        inventory=100,
        is_active=True
    )
    db_session.add(store_item)

    # 9. Store Item (Owned by DIFFERENT Teacher)
    other_teacher = Admin(username="teacher2", totp_secret="secret")
    db_session.add(other_teacher)
    db_session.flush()

    other_store_item = StoreItem(
        teacher_id=other_teacher.id,
        name="Foreign Item",
        price=Decimal('5.00'),
        inventory=100,
        is_active=True
    )
    db_session.add(other_store_item)

    # Give student some money
    tx = Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code=join_code,
        amount=Decimal('100.00'),
        account_type='checking',
        type='deposit',
        description='Initial funds',
        actor_membership_id=teacher_membership.id
    )
    db_session.add(tx)
    db_session.commit()

    # --- Test 1: Context Resolution ---
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        # We don't set current_join_code initially to test auto-selection

    # We need to access a route or call the function directly within request context
    with app.test_request_context('/'):
        # Manually set session for the current request context
        from flask import session
        session['student_id'] = student.id

        from app.routes.student import get_current_class_context, get_rent_settings_for_context

        context = get_current_class_context()
        assert context is not None
        assert context['join_code'] == join_code
        assert context['teacher_id'] == teacher.id
        assert context['block'] == "A"
        assert context['membership_id'] == student_membership.id

        # Test Rent Settings Resolution
        settings = get_rent_settings_for_context(context)
        assert settings is not None
        assert settings.id == rent_settings.id
        # Verify it used join_code (mocking query to ensure?)
        # We can trust it works if it returns the correct settings which has the join_code.

    # --- Test 2: Purchase Item (Success) ---
    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['login_time'] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    resp = client.post('/api/purchase-item', json={
        'item_id': store_item.id,
        'passphrase': 'pass',
        'quantity': 1
    })

    assert resp.status_code == 200
    assert resp.json['status'] == 'success'

    # Verify Transaction has actor_membership_id
    purchase_tx = Transaction.query.filter_by(type='purchase').first()
    assert purchase_tx is not None
    assert purchase_tx.actor_membership_id == student_membership.id
    assert purchase_tx.join_code == join_code

    # --- Test 3: Purchase Item (Cross-Class Leakage) ---
    # Attempt to buy item from other teacher
    resp = client.post('/api/purchase-item', json={
        'item_id': other_store_item.id,
        'passphrase': 'pass',
        'quantity': 1
    })

    # Should fail because item teacher_id != context teacher_id
    assert resp.status_code == 404 # "This item is not available"
    assert resp.json['status'] == 'error'

    print("All Phase A blocker tests passed!")

if __name__ == "__main__":
    sys.exit(pytest.main(["-v", "tests/test_phase_a_blockers.py"]))
