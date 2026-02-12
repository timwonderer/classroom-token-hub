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
    student_a2 = _create_student(teacher, 'Bo', 'JOINADMINA', block='A')
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
