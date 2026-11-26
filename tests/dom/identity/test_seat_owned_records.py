"""Shipping schema permits principal references only at Identity boundaries."""
from decimal import Decimal

import pytest
import sqlalchemy as sa

from tests.helpers.payroll_fixture import record_payroll_source_fixture
from app import db
from app.feats.base import FEATContext
from app.models import AttendanceSession, PayrollEvent, Seat, Transaction, User
from app.services.ledger_posting_service import create_pending_transaction
from app.services.payroll.settings import current_payroll_setting
from app.utils.student_deletion import delete_user_if_orphaned
from tests.helpers.classroom_initializer import initialize

ALLOWED = {('seats', 'user_id'), ('classes', 'teacher_user_id'),
           ('passkey_credentials', 'user_id'), ('recovery_requests', 'user_id'),
           ('credential_operations', 'user_id')}


def test_shipped_schema_has_only_identity_principal_references(client):
    inspector = sa.inspect(db.engine)
    actual = set()
    for table in inspector.get_table_names():
        for fk in inspector.get_foreign_keys(table):
            if fk['referred_table'] == 'users':
                actual.update((table, column) for column in fk['constrained_columns'])
        for column in inspector.get_columns(table):
            if column['name'] in {'user_id', 'teacher_id', 'sysadmin_id'} or column['name'].endswith('_user_id'):
                assert (table, column['name']) in ALLOWED
    assert actual == ALLOWED


def test_detaching_last_principal_preserves_seat_and_financial_productivity_facts(client):
    classroom = initialize('chemistry_p1', client.application)
    seat = classroom.students[0].seat
    seat_id, user_id = seat.id, seat.user_id
    with FEATContext('FEAT-PROD-003', idempotency_key='seat-history:setup'):
        transaction = create_pending_transaction(
            seat_id=seat_id, target_seat_id=seat_id, actor_seat_id=seat_id,
            class_id=classroom.class_id, mechanism='self', amount=Decimal('4.00'),
            account_type='checking', type='Deposit', description='Seat history')
        attendance = AttendanceSession(target_seat_id=seat_id, actor_seat_id=seat_id,
            class_id=classroom.class_id, status='active', reason_code='start_work')
        db.session.add(attendance); db.session.flush()
        setting = current_payroll_setting(classroom.class_id)
        payroll = record_payroll_source_fixture(class_id=classroom.class_id, target_seat_id=seat_id,
            actor_seat_id=classroom.teacher_seat.id, correlation_id='seat-history',
            idempotency_key='seat-history', policy_uuid=setting.policy_uuid,
            payroll_event_type='manual_credit')
        db.session.flush()
        record_ids = transaction.id, attendance.id, payroll.id
    with FEATContext('FEAT-TEST-SETUP', idempotency_key='seat-history:detach'):
        seat.user_id = None
        seat.claimed_at = None
        db.session.flush()
        assert delete_user_if_orphaned(user_id)
    db.session.expire_all()
    assert db.session.get(User, user_id) is None
    assert db.session.get(Seat, seat_id) is not None
    assert db.session.get(Transaction, record_ids[0]).amount == Decimal('4.00')
    assert db.session.get(AttendanceSession, record_ids[1]).target_seat_id == seat_id
    assert db.session.get(PayrollEvent, record_ids[2]).target_seat_id == seat_id
    # An existing authenticated principal may bind to this seat; old facts do not change.
    with FEATContext('FEAT-TEST-SETUP', idempotency_key='seat-history:rebind'):
        new_user = User(user_role='student', username_hash='seat-history-rebind-test')
        db.session.add(new_user); db.session.flush()
        db.session.get(Seat, seat_id).user_id = new_user.id
    assert db.session.get(Transaction, record_ids[0]).seat_id == seat_id


def test_principal_delete_cannot_cascade_away_a_bound_seat(client):
    classroom = initialize('chemistry_p1', client.application)
    seat = classroom.students[0].seat
    seat_id, user_id = seat.id, seat.user_id
    with pytest.raises(sa.exc.IntegrityError):
        with FEATContext('FEAT-TEST-SETUP', idempotency_key='seat-history:reject-delete'):
            User.query.filter_by(id=user_id).delete(synchronize_session=False)
    db.session.rollback()
    assert db.session.get(Seat, seat_id).user_id == user_id


def test_class_destroy_removes_seat_authored_announcements_and_policy_definitions(client):
    from app.models import Announcement, ClassEconomy, InsurancePolicy
    from app.services.announcement_service import create_class_announcement
    from app.services.insurance_definition_service import create_insurance_definition
    from tests.helpers.classroom_initializer import initialize_as_teacher
    from tests.dom.identity.helpers import admin_delete_class, valid_destruction_gate
    classroom = initialize_as_teacher('chemistry_p1', client, client.application)
    with FEATContext('FEAT-TEST-SETUP', idempotency_key='seat-author:setup'):
        announcement = create_class_announcement(created_by_seat_id=classroom.teacher_seat.id,
            class_id=classroom.class_id, title='Class note', message='Class message',
            priority='normal', is_active=True, expires_at=None)
        policy = create_insurance_definition(class_id=classroom.class_id,
            actor_seat_id=classroom.teacher_seat.id, definition={
                'title': 'Test policy', 'insurance_type': 'NON_MONETARY',
                'premium': Decimal('0.00'), 'charge_frequency': 'MONTHLY',
                'claims_per_week_equivalent': Decimal('1'), 'waiting_period_days': 3,
                'bill_preview_days': 3, 'nonpayment_mode': 'ACCUMULATE'})
        announcement_id, policy_uuid = announcement.id, policy.policy_uuid
    from app.routes.admin import _class_delete_confirmation_phrase
    response = admin_delete_class(client, **valid_destruction_gate(
        _class_delete_confirmation_phrase(db.session.get(ClassEconomy, classroom.class_id))))
    assert response.status_code == 200, response.get_data(as_text=True)
    db.session.expire_all()
    assert db.session.get(Announcement, announcement_id) is None
    assert db.session.get(InsurancePolicy, policy_uuid) is None
    assert db.session.get(ClassEconomy, classroom.class_id) is None


@pytest.mark.parametrize('record', ['announcement', 'product'])
def test_authors_cannot_be_borrowed_from_another_class(client, record):
    from app.services.announcement_service import create_class_announcement
    from app.services.store_service import publish_product, InvalidDefinition
    classroom = initialize('chemistry_p1', client.application)
    sibling = initialize('ap_csp_p3', client.application)
    with pytest.raises((ValueError, InvalidDefinition), match='teacher seat in this class'):
        with FEATContext('FEAT-TEST-SETUP', idempotency_key=f'seat-author:reject:{record}'):
            if record == 'announcement':
                create_class_announcement(created_by_seat_id=sibling.teacher_seat.id,
                    class_id=classroom.class_id, title='No', message='No',
                    priority='normal', is_active=True, expires_at=None)
            else:
                publish_product(class_id=classroom.class_id, actor_seat_id=sibling.teacher_seat.id,
                    definition={'name': 'No', 'price': Decimal('1.00'), 'item_type': 'delayed', 'economic_role': 'necessity'})


def test_operational_actor_logging_uses_scoped_seat_never_principal(app, caplog):
    from flask import g
    from types import SimpleNamespace
    from app.services import operational_event_service
    with app.test_request_context('/'):
        g.canonical_context = SimpleNamespace(user_id=918273, seat_id=456789, class_id='class-scope')
        operational_event_service.record(event_type='test', domain='test', class_id='class-scope')
        scoped = next(record for record in reversed(caplog.records) if record.msg == 'OPERATIONAL_EVENT %s').args
        # The line names the scoped seat by public id only; the internal seat,
        # class and principal ids never reach it (DOM-OPS-001 §7).
        assert 'actor_seat' in scoped and 'actor_seat_id' not in scoped
        assert 'user_id' not in scoped and 'class_id' not in scoped
        assert not any(value in (918273, 456789, 'class-scope') for value in scoped.values())
        operational_event_service.record(event_type='test', domain='test', class_id=None)
        unscoped = next(record for record in reversed(caplog.records) if record.msg == 'OPERATIONAL_EVENT %s').args
        assert unscoped['actor_seat'] == '-'
