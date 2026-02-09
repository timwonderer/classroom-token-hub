
import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from app.models import Admin, Student, Transaction, StoreItem, StudentItem, TeacherBlock, StudentTeacher
from app.extensions import db
from werkzeug.security import generate_password_hash

@pytest.fixture
def teacher_admin(client):
    admin = Admin(username="teacher_r", totp_secret="secret")
    db.session.add(admin)
    db.session.commit()
    return admin

@pytest.fixture
def student_in_class(client, teacher_admin):
    student = Student(first_name="TestRejection", last_initial="S", block="A", salt=b'salt')
    student.passphrase_hash = generate_password_hash('password')
    db.session.add(student)
    db.session.flush()

    link = StudentTeacher(student_id=student.id, admin_id=teacher_admin.id)
    db.session.add(link)
    
    seat = TeacherBlock(
        teacher_id=teacher_admin.id, block='A', join_code='REJECT123',
        student_id=student.id, is_claimed=True,
        first_name='TestRejection', last_initial='S', last_name_hash_by_part=[], dob_sum=0, salt=b'salt', first_half_hash='hash'
    )
    db.session.add(seat)
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
    client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 1
    })
    
    # Verify purchase deduction
    db.session.refresh(student)
    assert student.checking_balance == float(initial_balance - Decimal('15.00'))
    
    # Get the student item
    student_item = StudentItem.query.filter_by(student_id=student.id, store_item_id=item.id).first()
    assert student_item is not None
    assert student_item.status == 'purchased'
    
    # Request redemption
    client.post('/api/use-item', json={
        'student_item_id': student_item.id,
        'passphrase': 'password',
        'details': 'Please refund me'
    })
    
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
    assert student.checking_balance == float(initial_balance)
    
    # Item should be removed (or status changed to returned/refunded if you kept history, but plan said remove)
    # Checking if it's deleted as per plan "removed from the student's item list"
    # Although plan mentioned "removed from database (or marked returned)", let's see implementation.
    # Ideally soft delete or strict delete. Plan implies removal.
    item_check = db.session.get(StudentItem, student_item.id)
    assert item_check is None or item_check.status == 'returned'

    # Verify Refund Transaction
    refund_tx = Transaction.query.filter_by(
        student_id=student.id,
        type='refund',
        amount=Decimal('15.00')
    ).first()
    assert refund_tx is not None
    assert "Refund:" in refund_tx.description

