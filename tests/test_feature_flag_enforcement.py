"""
Test that feature flags properly block access to disabled features.

This ensures that when a teacher disables a feature (banking, payroll, etc.),
students cannot access those routes even via direct URL.
"""

import pytest
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash
from app.models import Student, Admin, Transaction, TeacherBlock, ClassEconomy, ClassFeature, PayrollReward, StoreItem
from app.extensions import db
from app.hash_utils import get_random_salt, hash_username


@pytest.fixture
def setup_student_with_disabled_banking(client):
    """Create a student with banking feature disabled."""
    # Create teacher
    teacher = Admin(
        username="teacher1",
        totp_secret="secret123"
    )
    db.session.add(teacher)
    db.session.commit()

    # Create student
    salt = get_random_salt()
    student = Student(
        first_name="Bob",
        last_initial="B",
        block="Period1",
        salt=salt,
        username_hash=hash_username("bob_b", salt),
        passphrase_hash=generate_password_hash("bob_pass")
    )
    db.session.add(student)
    db.session.flush()
    
    # Link student to teacher
    from app.models import StudentTeacher
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    db.session.commit()

    join_code = "MATH1B"
    
    # Create ClassEconomy first for FK constraint
    economy = ClassEconomy(
        join_code=join_code,
        teacher_id=teacher.id,
        display_name='Math Period 1B',
        created_by_admin_id=teacher.id
    )
    db.session.add(economy)
    db.session.flush()
    
    # Create TeacherBlock entry (claimed seat)
    seat = TeacherBlock(
        teacher_id=teacher.id,
        block="Period1",
        first_name="Bob",
        last_initial="B",
        last_name_hash_by_part=None,
        dob_sum_hash=None,
        salt=salt,
        first_half_hash="hash1",
        join_code=join_code,
        student_id=student.id,
        is_claimed=True,
        claimed_at=datetime.now(timezone.utc)
    )
    db.session.add(seat)
    db.session.commit()

    # Add some money to checking account
    tx = Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code=join_code,
        amount=100.0,
        account_type='checking',
        type='Initial',
        description='Starting balance'
    )
    db.session.add(tx)
    db.session.commit()

    for row in ClassFeature.query.filter(
        ClassFeature.class_id == economy.class_id,
        ClassFeature.feature_name.in_(["banking", "payroll"]),
    ).all():
        db.session.delete(row)
    db.session.commit()

    return {
        'teacher': teacher,
        'student': student,
        'join_code': join_code
    }


def test_transfer_blocked_when_banking_disabled(client, setup_student_with_disabled_banking):
    """Test that transfer route is blocked when banking is disabled."""
    data = setup_student_with_disabled_banking
    student = data['student']
    join_code = data['join_code']
    
    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        sess['current_period'] = 'Period1'
    
    # Try to access transfer page (GET)
    response = client.get('/student/transfer', follow_redirects=False)
    
    assert response.status_code == 404


def test_transfer_post_blocked_when_banking_disabled(client, setup_student_with_disabled_banking):
    """Test that transfer POST is blocked when banking is disabled."""
    data = setup_student_with_disabled_banking
    student = data['student']
    join_code = data['join_code']
    
    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        sess['current_period'] = 'Period1'
    
    # Try to submit a transfer (POST)
    response = client.post('/student/transfer', data={
        'from_account': 'checking',
        'to_account': 'savings',
        'amount': '50.00',
        'passphrase': 'bob_pass'
    }, follow_redirects=False)
    
    assert response.status_code == 404
    
    # Verify no transactions were created
    
    # Should only have the initial transaction, no transfer
    all_transactions = Transaction.query.filter_by(student_id=student.id).all()
    assert len(all_transactions) == 1
    assert all_transactions[0].type == 'Initial'


def test_payroll_blocked_when_payroll_disabled(client, setup_student_with_disabled_banking):
    """Test that payroll route is blocked when payroll is disabled."""
    data = setup_student_with_disabled_banking
    student = data['student']
    join_code = data['join_code']
    
    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        sess['current_period'] = 'Period1'
    
    # Try to access payroll page
    response = client.get('/student/payroll', follow_redirects=False)
    
    assert response.status_code == 404


@pytest.fixture
def setup_student_with_enabled_banking(client):
    """Create a student with banking feature enabled."""
    # Create teacher
    teacher = Admin(
        username="teacher2",
        totp_secret="secret456"
    )
    db.session.add(teacher)
    db.session.commit()

    # Create student
    salt = get_random_salt()
    student = Student(
        first_name="Carol",
        last_initial="C",
        block="Period2",
        salt=salt,
        username_hash=hash_username("carol_c", salt),
        passphrase_hash=generate_password_hash("carol_pass")
    )
    db.session.add(student)
    db.session.flush()

    # Link student to teacher
    from app.models import StudentTeacher
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    db.session.commit()

    join_code = "MATH2C"
    
    # Create ClassEconomy first for FK constraint
    economy = ClassEconomy(
        join_code=join_code,
        teacher_id=teacher.id,
        display_name='Math Period 2C',
        created_by_admin_id=teacher.id
    )
    db.session.add(economy)
    db.session.flush()
    
    # Create TeacherBlock entry (claimed seat)
    seat = TeacherBlock(
        teacher_id=teacher.id,
        block="Period2",
        first_name="Carol",
        last_initial="C",
        last_name_hash_by_part=None,
        dob_sum_hash=None,
        salt=salt,
        first_half_hash="hash2",
        join_code=join_code,
        student_id=student.id,
        is_claimed=True,
        claimed_at=datetime.now(timezone.utc)
    )
    db.session.add(seat)
    db.session.commit()

    # Add some money to checking account
    tx = Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code=join_code,
        amount=100.0,
        account_type='checking',
        type='Initial',
        description='Starting balance'
    )
    db.session.add(tx)
    db.session.commit()

    db.session.commit()

    return {
        'teacher': teacher,
        'student': student,
        'join_code': join_code
    }


def test_transfer_allowed_when_banking_enabled(client, setup_student_with_enabled_banking):
    """Test that transfer routes are not blocked by the feature flag when enabled."""
    data = setup_student_with_enabled_banking
    student = data['student']
    join_code = data['join_code']
    
    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        sess['current_period'] = 'Period2'
    
    # Access transfer page (GET) should work
    response = client.get('/student/transfer', follow_redirects=False)
    assert response.status_code == 200
    assert b'Transfer Details' in response.data or b'Finances' in response.data
    
    # Submit a transfer (POST) should not be blocked by the feature flag layer.
    response = client.post('/student/transfer', data={
        'from_account': 'checking',
        'to_account': 'savings',
        'amount': '50.00',
        'passphrase': 'carol_pass'
    }, follow_redirects=False)

    assert response.status_code == 302
    assert '/student/dashboard' in response.location or '/student/transfer' in response.location


def test_payroll_allowed_when_payroll_enabled(client, setup_student_with_enabled_banking):
    """Test that payroll works normally when payroll is enabled."""
    data = setup_student_with_enabled_banking
    student = data['student']
    join_code = data['join_code']
    
    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        sess['current_period'] = 'Period2'
    
    # Access payroll page should work
    response = client.get('/student/payroll', follow_redirects=False)
    assert response.status_code == 200
    assert b'Payroll' in response.data or b'payroll' in response.data


def test_admin_banking_rejects_disabled_class_scope(client):
    teacher = Admin(username="teacher_admin_feature_scope", totp_secret="secret789")
    db.session.add(teacher)
    db.session.commit()

    join_code = "BANKA1"
    economy = ClassEconomy(
        join_code=join_code,
        teacher_id=teacher.id,
        display_name='Banking Period A',
        created_by_admin_id=teacher.id,
    )
    db.session.add(economy)
    db.session.flush()

    db.session.add(TeacherBlock(
        teacher_id=teacher.id,
        block="A",
        first_name="Dana",
        last_initial="D",
        last_name_hash_by_part=None,
        dob_sum_hash=None,
        salt=b"saltbanking12345",
        first_half_hash="hash-banking-admin",
        join_code=join_code,
        is_claimed=False,
    ))

    for row in ClassFeature.query.filter_by(class_id=economy.class_id, feature_name='banking').all():
        db.session.delete(row)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher.id

    response = client.get('/admin/banking?settings_block=A')
    assert response.status_code == 404


def _create_admin_feature_scope(teacher, *, join_code, block, feature_name, enabled):
    economy = ClassEconomy(
        join_code=join_code,
        teacher_id=teacher.id,
        display_name=f'{feature_name.title()} Period {block}',
        created_by_admin_id=teacher.id,
    )
    db.session.add(economy)
    db.session.flush()

    db.session.add(TeacherBlock(
        teacher_id=teacher.id,
        block=block,
        first_name=f"{feature_name.title()}Student",
        last_initial="T",
        last_name_hash_by_part=None,
        dob_sum_hash=None,
        salt=f"salt-{feature_name}-{block}".encode("utf-8"),
        first_half_hash=f"hash-{feature_name}-{block}",
        join_code=join_code,
        is_claimed=False,
    ))

    if not enabled:
        for row in ClassFeature.query.filter_by(class_id=economy.class_id, feature_name=feature_name).all():
            db.session.delete(row)


def test_admin_store_rejects_disabled_class_scope(client):
    teacher = Admin(username="teacher_admin_store_scope", totp_secret="secret_store_scope")
    db.session.add(teacher)
    db.session.commit()

    _create_admin_feature_scope(teacher, join_code="STORE1", block="1", feature_name="store", enabled=True)
    _create_admin_feature_scope(teacher, join_code="STORE2", block="2", feature_name="store", enabled=False)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher.id

    response = client.get('/admin/store?join_code=STORE2')
    assert response.status_code == 404


def test_admin_hall_pass_rejects_disabled_class_scope(client):
    teacher = Admin(username="teacher_admin_hall_scope", totp_secret="secret_hall_scope")
    db.session.add(teacher)
    db.session.commit()

    _create_admin_feature_scope(teacher, join_code="HALL1", block="1", feature_name="hall_pass", enabled=True)
    _create_admin_feature_scope(teacher, join_code="HALL2", block="2", feature_name="hall_pass", enabled=False)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher.id

    response = client.get('/admin/hall-pass?join_code=HALL2')
    assert response.status_code == 404


def test_admin_payroll_rejects_disabled_class_scope(client):
    teacher = Admin(username="teacher_admin_payroll_scope", totp_secret="secret_payroll_scope")
    db.session.add(teacher)
    db.session.commit()

    _create_admin_feature_scope(teacher, join_code="PAY1", block="1", feature_name="payroll", enabled=True)
    _create_admin_feature_scope(teacher, join_code="PAY2", block="2", feature_name="payroll", enabled=False)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher.id

    response = client.get('/admin/payroll?join_code=PAY2')
    assert response.status_code == 404


def test_admin_payroll_reward_delete_rejects_disabled_class_scope(client):
    teacher = Admin(username="teacher_admin_payroll_reward_scope", totp_secret="secret_payroll_reward_scope")
    db.session.add(teacher)
    db.session.commit()

    _create_admin_feature_scope(teacher, join_code="PRW1", block="1", feature_name="payroll", enabled=True)
    _create_admin_feature_scope(teacher, join_code="PRW2", block="2", feature_name="payroll", enabled=False)
    reward = PayrollReward(
        teacher_id=teacher.id,
        name="Bonus",
        amount=5,
        is_active=True,
    )
    db.session.add(reward)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher.id

    response = client.post(f'/admin/payroll/rewards/{reward.id}/delete?join_code=PRW2')
    assert response.status_code == 404


def test_admin_store_delete_rejects_disabled_class_scope(client):
    teacher = Admin(username="teacher_admin_store_delete_scope", totp_secret="secret_store_delete_scope")
    db.session.add(teacher)
    db.session.commit()

    _create_admin_feature_scope(teacher, join_code="STD1", block="1", feature_name="store", enabled=True)
    _create_admin_feature_scope(teacher, join_code="STD2", block="2", feature_name="store", enabled=False)
    store_item = StoreItem(
        teacher_id=teacher.id,
        name="Pencil",
        description="Simple item",
        price=1,
        item_type='immediate',
        is_active=True,
    )
    db.session.add(store_item)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher.id

    response = client.post(f'/admin/store/delete/{store_item.id}?join_code=STD2', follow_redirects=False)
    assert response.status_code == 404


def test_student_rent_rejects_disabled_feature_scope(client):
    teacher = Admin(username="teacher_rent_disabled", totp_secret="secret999")
    db.session.add(teacher)
    db.session.commit()

    salt = get_random_salt()
    student = Student(
        first_name="Riley",
        last_initial="R",
        block="Period3",
        salt=salt,
        username_hash=hash_username("riley_r", salt),
        passphrase_hash=generate_password_hash("riley_pass"),
        is_rent_enabled=True,
    )
    db.session.add(student)
    db.session.flush()

    from app.models import StudentTeacher
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))

    join_code = "RENT03"
    economy = ClassEconomy(
        join_code=join_code,
        teacher_id=teacher.id,
        display_name='Rent Period 3',
        created_by_admin_id=teacher.id,
    )
    db.session.add(economy)
    db.session.flush()

    db.session.add(TeacherBlock(
        teacher_id=teacher.id,
        block="Period3",
        first_name="Riley",
        last_initial="R",
        last_name_hash_by_part=None,
        dob_sum_hash=None,
        salt=salt,
        first_half_hash="hash-rent-student",
        join_code=join_code,
        student_id=student.id,
        is_claimed=True,
        claimed_at=datetime.now(timezone.utc)
    ))

    for row in ClassFeature.query.filter_by(class_id=economy.class_id, feature_name='rent').all():
        db.session.delete(row)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        sess['current_period'] = 'Period3'

    response = client.get('/student/rent', follow_redirects=False)
    assert response.status_code == 404
