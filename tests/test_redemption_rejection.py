
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from decimal import Decimal
from datetime import datetime, timezone
from app.models import Admin, Student, Transaction, StoreItem, StudentItem, TeacherBlock, StudentTeacher, ClassEconomy, ClassMembership
from app.extensions import db
from werkzeug.security import generate_password_hash

@pytest.fixture
def teacher_admin(client):
    admin = make_admin("teacher_r", "secret")
    db.session.add(admin)
    db.session.commit()
    return admin

@pytest.fixture
def student_in_class(client, teacher_admin):
    student = Student(first_name="TestRejection", last_initial="S", block="A", salt=b'salt')
    student.passphrase_hash = generate_password_hash('password')
    db.session.add(student)
    db.session.flush()

    link = StudentTeacher(student_id=student.id, teacher_id=teacher_admin.id)
    db.session.add(link)
    
    seat = TeacherBlock(
        teacher_id=teacher_admin.id, block='A', join_code='REJECT123',
        student_id=student.id, is_claimed=True,
        first_name='TestRejection', last_initial='S', last_name_hash_by_part=None, dob_sum_hash=None, salt=b'salt', first_half_hash='hash'
    )
    db.session.add(seat)
    db.session.add(seat)
    
    # Setup Class Context
    db.session.add(ClassEconomy(join_code='REJECT123', teacher_id=teacher_admin.id, status="active", created_by_admin_id=teacher_admin.id))
    db.session.add(ClassMembership(join_code='REJECT123', admin_id=teacher_admin.id, role="admin"))
    db.session.add(ClassMembership(join_code='REJECT123', student_id=student.id, role="student"))
    db.session.commit()
    return student

def test_reject_redemption_refunds_student(client, teacher_admin, student_in_class):
    """Test that rejecting a redemption refunds the student and removes the item."""
    student = student_in_class
    
    # 1. Setup Item and Purchase
    # Create item
    item = StoreItem(
        teacher_id=teacher_admin.id, 
        name='Refundable Item', 
        price=Decimal('15.00'),
        item_type='delayed',
        is_active=True
    )
    db.session.add(item)
    db.session.flush()
    
    # Give student enough money
    initial_balance = Decimal('100.00')
    tx = Transaction(
        student_id=student.id, 
        teacher_id=teacher_admin.id, 
        join_code='REJECT123',
        amount=initial_balance, 
        account_type='checking',
        type='deposit',
        description='Initial funds'
    )
    db.session.add(tx)
    db.session.commit()
    
    # Login as student to purchase
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = 'REJECT123'
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        
    # Purchase item
    purchase_resp = client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 1
    })
    assert purchase_resp.status_code == 200
    assert purchase_resp.json['status'] == 'success'
    
    # Verify purchase deduction
    db.session.refresh(student)
    assert student.checking_balance == initial_balance - Decimal('15.00')
    
    # Get the student item
    student_item = StudentItem.query.filter_by(student_id=student.id, store_item_id=item.id).first()
    assert student_item is not None
    assert student_item.status == 'purchased'
    
    # Request redemption
    use_resp = client.post('/api/use-item', json={
        'student_item_id': student_item.id,
        'passphrase': 'password',
        'details': 'Please refund me'
    })
    assert use_resp.status_code == 200
    assert use_resp.json['status'] == 'success'
    
    db.session.refresh(student_item)
    assert student_item.status == 'processing'
    
    # 2. Reject Redemption (Admin Action)
    # Login as teacher
    with client.session_transaction() as sess:
        sess['admin_id'] = teacher_admin.id
        sess['is_admin'] = True
        
    # Call rejection endpoint
    resp = client.post('/api/reject-redemption', json={'student_item_id': student_item.id})
    
    # Assert success
    assert resp.status_code == 200
    assert resp.json['status'] == 'success'
    
    # 3. Verify Refund
    db.session.refresh(student)
    # Balance should be back to initial (100)
    assert student.checking_balance == initial_balance
    
    # Item should no longer be active in inventory; keep history as rejected.
    item_check = db.session.get(StudentItem, student_item.id)
    assert item_check is not None
    assert item_check.status == 'rejected'

    # Verify Refund Transaction
    refund_tx = Transaction.query.filter_by(
        student_id=student.id,
        type='refund',
        amount=Decimal('15.00')
    ).first()
    assert refund_tx is not None
    assert "Refund:" in refund_tx.description
    purchase_tx = Transaction.query.filter_by(
        student_id=student.id,
        type='purchase',
    ).filter(Transaction.description.like('Purchase: Refundable Item%')).first()
    assert purchase_tx is not None
    assert refund_tx.original_transaction_id == purchase_tx.id


def test_reject_redemption_refunds_single_unit_from_multi_quantity_purchase(client, teacher_admin, student_in_class):
    """Ensure a rejected redemption refunds only one unit from a multi-quantity purchase."""
    student = student_in_class

    item = StoreItem(
        teacher_id=teacher_admin.id,
        name='Bulk Item',
        price=Decimal('10.00'),
        item_type='delayed',
        is_active=True
    )
    db.session.add(item)
    db.session.flush()

    initial_balance = Decimal('100.00')
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher_admin.id,
        join_code='REJECT123',
        amount=initial_balance,
        account_type='checking',
        type='deposit',
        description='Initial funds'
    ))
    db.session.commit()

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = 'REJECT123'
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    purchase_resp = client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 3
    })
    assert purchase_resp.status_code == 200
    assert purchase_resp.json['status'] == 'success'

    db.session.refresh(student)
    assert student.checking_balance == initial_balance - Decimal('30.00')

    student_item = StudentItem.query.filter_by(student_id=student.id, store_item_id=item.id).first()
    assert student_item is not None

    use_resp = client.post('/api/use-item', json={
        'student_item_id': student_item.id,
        'passphrase': 'password',
        'details': 'Use one from bulk'
    })
    assert use_resp.status_code == 200
    assert use_resp.json['status'] == 'success'

    db.session.refresh(student_item)
    assert student_item.status == 'processing'

    with client.session_transaction() as sess:
        sess['admin_id'] = teacher_admin.id
        sess['is_admin'] = True

    resp = client.post('/api/reject-redemption', json={'student_item_id': student_item.id})
    assert resp.status_code == 200
    assert resp.json['status'] == 'success'

    db.session.refresh(student)
    assert student.checking_balance == initial_balance - Decimal('20.00')

    refund_tx = Transaction.query.filter_by(
        student_id=student.id,
        type='refund',
        amount=Decimal('10.00')
    ).first()
    assert refund_tx is not None


def test_reject_redemption_legacy_item_resolves_join_code(client, teacher_admin, student_in_class):
    """Legacy StudentItem with NULL join_code should refund with purchase join_code."""
    student = student_in_class

    item = StoreItem(
        teacher_id=teacher_admin.id,
        name='Legacy Item',
        price=Decimal('12.00'),
        item_type='delayed',
        is_active=True
    )
    db.session.add(item)
    db.session.flush()

    purchase_tx = Transaction(
        student_id=student.id,
        teacher_id=teacher_admin.id,
        join_code='REJECT123',
        amount=Decimal('-12.00'),
        account_type='checking',
        type='purchase',
        description='Purchase: Legacy Item'
    )
    db.session.add(purchase_tx)
    db.session.flush()

    legacy_item = StudentItem(
        student_id=student.id,
        store_item_id=item.id,
        join_code='REJECT123',
        status='processing',
        purchase_date=datetime.now(timezone.utc)
    )
    db.session.add(legacy_item)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['admin_id'] = teacher_admin.id
        sess['is_admin'] = True

    resp = client.post('/api/reject-redemption', json={'student_item_id': legacy_item.id})
    assert resp.status_code == 200
    assert resp.json['status'] == 'success'

    refund_tx = Transaction.query.filter_by(
        student_id=student.id,
        type='refund',
        amount=Decimal('12.00')
    ).first()
    assert refund_tx is not None
    assert refund_tx.join_code == 'REJECT123'
