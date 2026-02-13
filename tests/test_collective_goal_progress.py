from datetime import datetime, timezone
from decimal import Decimal

from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Admin, StoreItem, Student, StudentItem, StudentTeacher, TeacherBlock, Transaction


def _login_student(client, student_id, join_code):
    with client.session_transaction() as sess:
        sess['student_id'] = student_id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()


def _login_admin(client, admin_id):
    with client.session_transaction() as sess:
        sess['admin_id'] = admin_id
        sess['is_admin'] = True


def _create_student(teacher, first_name, join_code, block='A'):
    student = Student(first_name=first_name, last_initial='S', block=block, salt=b'salt')
    student.passphrase_hash = generate_password_hash('password')
    db.session.add(student)
    db.session.flush()
    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher.id))
    db.session.add(TeacherBlock(
        teacher_id=teacher.id,
        block=block,
        join_code=join_code,
        student_id=student.id,
        is_claimed=True,
        first_name=first_name,
        last_initial='S',
        last_name_hash_by_part=[],
        dob_sum=0,
        salt=b'salt',
        first_half_hash=f'hash_{first_name}_{join_code}',
    ))
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code=join_code,
        amount=Decimal('100.00'),
        account_type='checking',
        type='deposit',
        description='Initial funds',
    ))
    return student


def test_student_shop_collective_progress_counts_current_class_only(client):
    teacher = Admin(username='teacher_collective_shop', totp_secret='secret')
    db.session.add(teacher)
    db.session.flush()

    student_a1 = _create_student(teacher, 'Alice', 'JOINA123', block='A')
    student_a2 = _create_student(teacher, 'Ben', 'JOINA123', block='A')
    student_b1 = _create_student(teacher, 'Cara', 'JOINB456', block='B')
    db.session.flush()

    item = StoreItem(
        teacher_id=teacher.id,
        name='Class Pizza Party',
        price=Decimal('10.00'),
        item_type='collective',
        collective_goal_type='fixed',
        collective_goal_target=2,
        is_active=True,
    )
    db.session.add(item)
    db.session.flush()

    # One purchaser in class A and one purchaser in class B.
    db.session.add_all([
        StudentItem(student_id=student_a1.id, store_item_id=item.id, join_code='JOINA123', status='pending'),
        StudentItem(student_id=student_b1.id, store_item_id=item.id, join_code='JOINB456', status='pending'),
    ])
    db.session.commit()

    _login_student(client, student_a2.id, 'JOINA123')
    resp = client.get('/student/shop')
    assert resp.status_code == 200
    # Must show progress for class A only, not include class B purchases.
    assert b'1/2' in resp.data


def test_collective_unlock_scoped_to_join_code_and_goal_type(client):
    teacher = Admin(username='teacher_collective_unlock', totp_secret='secret')
    db.session.add(teacher)
    db.session.flush()

    student_a1 = _create_student(teacher, 'Alex', 'JOINA777', block='A')
    student_a2 = _create_student(teacher, 'Bri', 'JOINA777', block='A')
    student_b1 = _create_student(teacher, 'Cy', 'JOINB999', block='B')
    db.session.flush()

    item = StoreItem(
        teacher_id=teacher.id,
        name='Collective Unlock',
        price=Decimal('10.00'),
        item_type='collective',
        collective_goal_type='fixed',
        collective_goal_target=2,
        is_active=True,
    )
    db.session.add(item)
    db.session.flush()

    # Existing purchase in class A and class B.
    db.session.add_all([
        StudentItem(student_id=student_a1.id, store_item_id=item.id, join_code='JOINA777', status='pending'),
        StudentItem(student_id=student_b1.id, store_item_id=item.id, join_code='JOINB999', status='pending'),
    ])
    db.session.commit()

    _login_student(client, student_a2.id, 'JOINA777')
    purchase_resp = client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert purchase_resp.status_code == 200

    class_a_statuses = [
        si.status for si in StudentItem.query.filter_by(store_item_id=item.id, join_code='JOINA777').all()
    ]
    class_b_statuses = [
        si.status for si in StudentItem.query.filter_by(store_item_id=item.id, join_code='JOINB999').all()
    ]

    # Class A reached fixed goal of 2 students, so pending purchases unlock to processing.
    assert all(status == 'processing' for status in class_a_statuses)
    # Class B progress should not be modified by class A purchase.
    assert class_b_statuses == ['pending']


def test_admin_store_shows_collective_progress(client):
    teacher = Admin(username='teacher_collective_admin', totp_secret='secret')
    db.session.add(teacher)
    db.session.flush()

    student_a1 = _create_student(teacher, 'Ana', 'JOINADMINA', block='A')
    _create_student(teacher, 'Bo', 'JOINADMINA', block='A')
    db.session.flush()

    item = StoreItem(
        teacher_id=teacher.id,
        name='Admin Progress Item',
        price=Decimal('5.00'),
        item_type='collective',
        collective_goal_type='fixed',
        collective_goal_target=2,
        is_active=True,
    )
    db.session.add(item)
    db.session.flush()
    db.session.add(StudentItem(student_id=student_a1.id, store_item_id=item.id, join_code='JOINADMINA', status='pending'))
    db.session.commit()

    _login_admin(client, teacher.id)
    resp = client.get('/admin/store')
    assert resp.status_code == 200
    assert b'Collective Progress' in resp.data
    assert b'1/2' in resp.data


def test_whole_class_collective_prevents_duplicate_purchase(client):
    """Test that students can only purchase a whole_class collective item once."""
    teacher = Admin(username='teacher_whole_class', totp_secret='secret')
    db.session.add(teacher)
    db.session.flush()

    student_a1 = _create_student(teacher, 'Dana', 'JOINWHOLE', block='A')
    student_a2 = _create_student(teacher, 'Eve', 'JOINWHOLE', block='A')
    db.session.flush()

    item = StoreItem(
        teacher_id=teacher.id,
        name='Whole Class Goal Item',
        price=Decimal('10.00'),
        item_type='collective',
        collective_goal_type='whole_class',
        is_active=True,
    )
    db.session.add(item)
    db.session.commit()

    _login_student(client, student_a1.id, 'JOINWHOLE')
    
    # First purchase should succeed
    resp1 = client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert resp1.status_code == 200
    
    # Second purchase by same student should fail
    resp2 = client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert resp2.status_code == 400
    json_data = resp2.get_json()
    assert 'already purchased' in json_data['message'].lower()


def test_whole_class_collective_goal_uses_correct_class_size(client):
    """Test that whole_class collective goals use actual student count, not seat count."""
    teacher = Admin(username='teacher_class_size', totp_secret='secret')
    db.session.add(teacher)
    db.session.flush()

    # Create 2 students for the class
    student_a1 = _create_student(teacher, 'Frank', 'JOINSIZE', block='A')
    student_a2 = _create_student(teacher, 'Grace', 'JOINSIZE', block='A')
    db.session.flush()

    item = StoreItem(
        teacher_id=teacher.id,
        name='Whole Class Pizza',
        price=Decimal('5.00'),
        item_type='collective',
        collective_goal_type='whole_class',
        is_active=True,
    )
    db.session.add(item)
    db.session.commit()

    # First student purchases
    _login_student(client, student_a1.id, 'JOINSIZE')
    resp1 = client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert resp1.status_code == 200
    
    # Check that the goal shows 1/2
    resp_shop1 = client.get('/student/shop')
    assert b'1/2' in resp_shop1.data
    
    # Second student purchases - goal should be reached (2/2)
    _login_student(client, student_a2.id, 'JOINSIZE')
    resp2 = client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert resp2.status_code == 200
    
    # Check all items are now processing (goal reached)
    items = StudentItem.query.filter_by(store_item_id=item.id, join_code='JOINSIZE').all()
    assert len(items) == 2
    assert all(si.status == 'processing' for si in items)


def test_collective_progress_with_correct_roster_count_admin(client):
    """Test that admin view shows correct class size based on actual students."""
    teacher = Admin(username='teacher_admin_size', totp_secret='secret')
    db.session.add(teacher)
    db.session.flush()

    # Create 3 students
    student_a1 = _create_student(teacher, 'Henry', 'JOINADMIN', block='A')
    student_a2 = _create_student(teacher, 'Iris', 'JOINADMIN', block='A')
    student_a3 = _create_student(teacher, 'Jack', 'JOINADMIN', block='A')
    db.session.flush()

    item = StoreItem(
        teacher_id=teacher.id,
        name='Admin Whole Class Item',
        price=Decimal('5.00'),
        item_type='collective',
        collective_goal_type='whole_class',
        is_active=True,
    )
    db.session.add(item)
    db.session.flush()
    
    # One student purchases
    db.session.add(StudentItem(student_id=student_a1.id, store_item_id=item.id, join_code='JOINADMIN', status='pending'))
    db.session.commit()

    _login_admin(client, teacher.id)
    resp = client.get('/admin/store')
    assert resp.status_code == 200
    # Should show 1/3 (1 purchase out of 3 students)
    assert b'1/3' in resp.data


def test_fixed_collective_allows_multiple_purchases(client):
    """Test that fixed collective goals still allow multiple purchases from same student."""
    teacher = Admin(username='teacher_fixed_multi', totp_secret='secret')
    db.session.add(teacher)
    db.session.flush()

    student_a1 = _create_student(teacher, 'Kelly', 'JOINFIXED', block='A')
    db.session.flush()

    item = StoreItem(
        teacher_id=teacher.id,
        name='Fixed Goal Item',
        price=Decimal('5.00'),
        item_type='collective',
        collective_goal_type='fixed',
        collective_goal_target=3,
        is_active=True,
    )
    db.session.add(item)
    db.session.commit()

    _login_student(client, student_a1.id, 'JOINFIXED')
    
    # First purchase should succeed
    resp1 = client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert resp1.status_code == 200
    
    # Second purchase by same student should also succeed for fixed goals
    resp2 = client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert resp2.status_code == 200
    
    # But progress should only count 1 unique student
    resp_shop = client.get('/student/shop')
    assert b'1/3' in resp_shop.data

