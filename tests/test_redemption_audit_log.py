from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (
    Admin,
    RedemptionAuditAction,
    RedemptionAuditLog,
    RedemptionAuditSource,
    StoreItem,
    Student,
    StudentItem,
    StudentTeacher,
    TeacherBlock,
    Transaction,
)


@pytest.fixture
def teacher_admin(client):
    admin = Admin(username="audit_teacher", totp_secret="secret")
    db.session.add(admin)
    db.session.commit()
    return admin


@pytest.fixture
def student_in_class(client, teacher_admin):
    student = Student(first_name="Audit", last_initial="S", block="A", salt=b'salt')
    student.passphrase_hash = generate_password_hash('password')
    db.session.add(student)
    db.session.flush()

    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher_admin.id))
    db.session.add(TeacherBlock(
        teacher_id=teacher_admin.id,
        block='A',
        join_code='AUDIT123',
        student_id=student.id,
        is_claimed=True,
        first_name='Audit',
        last_initial='S',
        last_name_hash_by_part=[],
        dob_sum=0,
        salt=b'salt',
        first_half_hash='hash',
    ))
    db.session.commit()
    return student


def _login_student(client, student_id):
    with client.session_transaction() as sess:
        sess['student_id'] = student_id
        sess['current_join_code'] = 'AUDIT123'
        sess['login_time'] = datetime.now(timezone.utc).isoformat()


def _login_admin(client, admin_id):
    with client.session_transaction() as sess:
        sess['admin_id'] = admin_id
        sess['is_admin'] = True


def _fund_and_purchase_delayed_item(client, teacher_admin, student, item_name='Audit Item', price=Decimal('10.00')):
    item = StoreItem(
        teacher_id=teacher_admin.id,
        name=item_name,
        price=price,
        item_type='delayed',
        is_active=True,
    )
    db.session.add(item)
    db.session.flush()
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher_admin.id,
        join_code='AUDIT123',
        amount=Decimal('100.00'),
        account_type='checking',
        type='deposit',
        description='Initial funds',
    ))
    db.session.commit()

    _login_student(client, student.id)
    purchase_resp = client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert purchase_resp.status_code == 200
    assert purchase_resp.json['status'] == 'success'

    student_item = StudentItem.query.filter_by(student_id=student.id, store_item_id=item.id).first()
    assert student_item is not None
    return item, student_item


def test_request_approve_reject_write_audit_rows(client, teacher_admin, student_in_class):
    student = student_in_class

    # Request + approve flow
    _, student_item = _fund_and_purchase_delayed_item(client, teacher_admin, student, item_name='Approval Item')
    use_resp = client.post('/api/use-item', json={
        'student_item_id': student_item.id,
        'passphrase': 'password',
        'details': 'approve note',
    })
    assert use_resp.status_code == 200
    assert use_resp.json['status'] == 'success'

    request_rows = RedemptionAuditLog.query.filter_by(student_item_id=student_item.id, action=RedemptionAuditAction.REQUEST).all()
    assert len(request_rows) == 1
    assert request_rows[0].notes == 'approve note'
    assert request_rows[0].source == RedemptionAuditSource.LIVE

    _login_admin(client, teacher_admin.id)
    approve_resp = client.post('/api/approve-redemption', json={'student_item_id': student_item.id})
    assert approve_resp.status_code == 200
    assert approve_resp.json['status'] == 'success'

    approved_rows = RedemptionAuditLog.query.filter_by(student_item_id=student_item.id, action=RedemptionAuditAction.APPROVED).all()
    assert len(approved_rows) == 1

    # Separate reject flow
    _login_student(client, student.id)
    _, reject_item = _fund_and_purchase_delayed_item(client, teacher_admin, student, item_name='Reject Item')
    reject_use_resp = client.post('/api/use-item', json={
        'student_item_id': reject_item.id,
        'passphrase': 'password',
        'details': 'reject me',
    })
    assert reject_use_resp.status_code == 200

    _login_admin(client, teacher_admin.id)
    reject_resp = client.post('/api/reject-redemption', json={'student_item_id': reject_item.id})
    assert reject_resp.status_code == 200
    assert reject_resp.json['status'] == 'success'

    rejected_rows = RedemptionAuditLog.query.filter_by(action=RedemptionAuditAction.REJECTED).all()
    assert len(rejected_rows) == 1
    assert rejected_rows[0].notes is not None
    assert 'reject me' in rejected_rows[0].notes


def test_audit_helper_called_once_per_action(client, teacher_admin, student_in_class, monkeypatch):
    student = student_in_class
    _, student_item = _fund_and_purchase_delayed_item(client, teacher_admin, student, item_name='Count Item')

    import app.routes.api as api_module
    original_helper = api_module._append_redemption_audit_log
    calls = {'count': 0}

    def wrapped_helper(**kwargs):
        calls['count'] += 1
        return original_helper(**kwargs)

    monkeypatch.setattr(api_module, '_append_redemption_audit_log', wrapped_helper)

    use_resp = client.post('/api/use-item', json={
        'student_item_id': student_item.id,
        'passphrase': 'password',
        'details': 'single request call',
    })
    assert use_resp.status_code == 200
    assert calls['count'] == 1


def test_no_mutation_if_audit_insert_fails_request_flow(client, teacher_admin, student_in_class, monkeypatch):
    student = student_in_class
    _, student_item = _fund_and_purchase_delayed_item(client, teacher_admin, student, item_name='Fail Request')
    original_status = student_item.status

    import app.routes.api as api_module

    def fail_helper(**kwargs):
        raise SQLAlchemyError("forced failure")

    monkeypatch.setattr(api_module, '_append_redemption_audit_log', fail_helper)

    resp = client.post('/api/use-item', json={
        'student_item_id': student_item.id,
        'passphrase': 'password',
        'details': 'should fail before mutation',
    })
    assert resp.status_code == 500

    db.session.refresh(student_item)
    assert student_item.status == original_status
    assert RedemptionAuditLog.query.count() == 0


def test_no_mutation_if_audit_insert_fails_approve_reject(client, teacher_admin, student_in_class, monkeypatch):
    student = student_in_class
    _, student_item = _fund_and_purchase_delayed_item(client, teacher_admin, student, item_name='Fail Finalize')

    use_resp = client.post('/api/use-item', json={
        'student_item_id': student_item.id,
        'passphrase': 'password',
        'details': 'finalize',
    })
    assert use_resp.status_code == 200

    # Clear successful request audit row to isolate this test's assertion.
    RedemptionAuditLog.query.delete()
    db.session.commit()

    import app.routes.api as api_module

    def fail_helper(**kwargs):
        raise SQLAlchemyError("forced failure")

    monkeypatch.setattr(api_module, '_append_redemption_audit_log', fail_helper)
    _login_admin(client, teacher_admin.id)

    approve_resp = client.post('/api/approve-redemption', json={'student_item_id': student_item.id})
    assert approve_resp.status_code == 500
    db.session.refresh(student_item)
    assert student_item.status == 'processing'
    assert RedemptionAuditLog.query.count() == 0

    reject_resp = client.post('/api/reject-redemption', json={'student_item_id': student_item.id})
    assert reject_resp.status_code == 500
    db.session.refresh(student_item)
    assert student_item.status == 'processing'
    assert Transaction.query.filter_by(student_id=student.id, type='refund').count() == 0
    assert RedemptionAuditLog.query.count() == 0


def test_legacy_adapter_shows_inferred_without_persisting(client, teacher_admin, student_in_class):
    student = student_in_class

    item = StoreItem(
        teacher_id=teacher_admin.id,
        name='Legacy-Like Item',
        price=Decimal('5.00'),
        item_type='delayed',
        is_active=True,
    )
    db.session.add(item)
    db.session.flush()
    db.session.add(StudentItem(
        student_id=student.id,
        store_item_id=item.id,
        join_code='AUDIT123',
        status='completed',
        redemption_details='legacy note',
    ))
    db.session.commit()

    _login_admin(client, teacher_admin.id)
    before_count = RedemptionAuditLog.query.count()
    resp = client.get('/admin/store')
    assert resp.status_code == 200
    assert b'Legacy' in resp.data
    assert RedemptionAuditLog.query.count() == before_count
