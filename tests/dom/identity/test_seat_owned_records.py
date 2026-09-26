"""Shipping schema permits principal references only at Identity boundaries."""
from decimal import Decimal
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app import db
from app.feats.base import FEATContext
from app.models import AttendanceSession, PayrollEvent, PolicyVersion, Seat, Transaction, User
from app.services.ledger_posting_service import create_pending_transaction
from app.utils.student_deletion import delete_user_if_orphaned
from tests.helpers.classroom_initializer import initialize

ALLOWED = {('seats', 'user_id'), ('classes', 'teacher_user_id'),
           ('passkey_credentials', 'user_id'), ('recovery_requests', 'user_id')}


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
    with FEATContext('FEAT-TEST-SETUP', idempotency_key='seat-history:setup'):
        transaction = create_pending_transaction(
            seat_id=seat_id, target_seat_id=seat_id, actor_seat_id=seat_id,
            class_id=classroom.class_id, mechanism='self', amount=Decimal('4.00'),
            account_type='checking', type='Deposit', description='Seat history')
        attendance = AttendanceSession(target_seat_id=seat_id, actor_seat_id=seat_id,
            class_id=classroom.class_id, status='active', reason_code='start_work')
        policy = PolicyVersion(class_id=classroom.class_id, domain='seat-lifetime-test',
            version_number=1, policy_payload_json='{}')
        db.session.add_all([attendance, policy]); db.session.flush()
        payroll = PayrollEvent(class_id=classroom.class_id, target_seat_id=seat_id,
            actor_seat_id=classroom.teacher_seat.id, correlation_id='seat-history',
            idempotency_key='seat-history', policy_version_id=policy.id,
            policy_uuid=policy.policy_uuid, payroll_event_type='manual_credit')
        db.session.add(payroll); db.session.flush()
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


def _migration(conn):
    path = Path(__file__).resolve().parents[3] / 'migrations/versions/c7a7b8c9d0e1_seat_owned_records.py'
    spec = importlib.util.spec_from_file_location('seat_migration_test', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.op = Operations(MigrationContext.configure(conn))
    return module


def test_migration_maps_author_only_with_exact_class_teacher_binding(client):
    classroom = initialize('chemistry_p1', client.application)
    with db.engine.connect() as conn:
        transaction = conn.begin()
        try:
            conn.execute(sa.text('CREATE TABLE legacy_authors (id INT, class_id TEXT, user_id INT)'))
            conn.execute(sa.text('INSERT INTO legacy_authors VALUES (1, :class_id, :user_id)'),
                         {'class_id': classroom.class_id, 'user_id': classroom.teacher_user.id})
            _migration(conn)._replace_author(conn, 'legacy_authors', 'user_id', 'created_by_seat_id', nullable=False)
            assert conn.execute(sa.text('SELECT created_by_seat_id FROM legacy_authors')).scalar() == classroom.teacher_seat.id
            assert 'user_id' not in {c['name'] for c in sa.inspect(conn).get_columns('legacy_authors')}
        finally:
            transaction.rollback()


def test_migration_rejects_an_author_outside_the_class(client):
    classroom = initialize('chemistry_p1', client.application)
    with db.engine.connect() as conn:
        transaction = conn.begin()
        try:
            conn.execute(sa.text('CREATE TABLE legacy_authors (id INT, class_id TEXT, user_id INT)'))
            conn.execute(sa.text('INSERT INTO legacy_authors VALUES (1, :class_id, :user_id)'),
                         {'class_id': classroom.class_id, 'user_id': classroom.students[0].user.id})
            with pytest.raises(RuntimeError, match='exactly one teacher seat'):
                _migration(conn)._replace_author(conn, 'legacy_authors', 'user_id', 'created_by_seat_id', nullable=False)
        finally:
            transaction.rollback()


def test_migration_refuses_legacy_bulk_replay_without_rewriting_history(client):
    from app.services.ledger_command_service import create_reserved_effects
    classroom = initialize('chemistry_p1', client.application)
    effects = [{'seat_id': s.seat.id, 'target_seat_id': s.seat.id,
                'actor_seat_id': classroom.teacher_seat.id, 'class_id': classroom.class_id,
                'mechanism': 'teacher', 'amount': Decimal('2.00'), 'account_type': 'checking',
                'type': 'manual_payment', 'description': 'Bulk bonus'}
               for s in classroom.students[:2]]
    with FEATContext('FEAT-TEST-SETUP', idempotency_key='migration:bulk'):
        rows, _ = create_reserved_effects(class_id=classroom.class_id,
            feat_code='FEAT-TEST-SETUP', idempotency_key='migration:bulk', effects=effects)
        reservation_id = rows[0].command_reservation_id
    with db.engine.connect() as conn:
        transaction = conn.begin()
        try:
            conn.execute(sa.text('UPDATE ledger_command_reservation SET fingerprint_version=2 WHERE id=:id'),
                         {'id': reservation_id})
            before = conn.execute(sa.text('SELECT replay_fingerprint FROM ledger_command_reservation WHERE id=:id'), {'id': reservation_id}).scalar()
            with pytest.raises(RuntimeError, match='legacy multi-effect replay history'):
                _migration(conn).upgrade()
            assert conn.execute(sa.text('SELECT replay_fingerprint FROM ledger_command_reservation WHERE id=:id'), {'id': reservation_id}).scalar() == before
        finally:
            transaction.rollback()


def test_class_destroy_removes_seat_authored_announcements_and_policy_lineage(client):
    from app.models import Announcement, PolicyTransition, ClassEconomy
    from app.services.announcement_service import create_class_announcement
    from app.services.insurance_policy_service import create_policy_version
    from tests.helpers.classroom_initializer import initialize_as_teacher
    from tests.dom.identity.helpers import admin_delete_class, valid_destruction_gate
    classroom = initialize_as_teacher('chemistry_p1', client, client.application)
    with FEATContext('FEAT-TEST-SETUP', idempotency_key='seat-author:setup'):
        announcement = create_class_announcement(created_by_seat_id=classroom.teacher_seat.id,
            class_id=classroom.class_id, title='Class note', message='Class message',
            priority='normal', is_active=True, expires_at=None)
        version = create_policy_version(class_id=classroom.class_id,
            actor_seat_id=classroom.teacher_seat.id, payload={'name': 'Test policy'})
        announcement_id, version_id = announcement.id, version.id
        transition_id = version.created_by_transition_id
    from app.routes.admin import _class_delete_confirmation_phrase
    response = admin_delete_class(client, **valid_destruction_gate(
        _class_delete_confirmation_phrase(db.session.get(ClassEconomy, classroom.class_id))))
    assert response.status_code == 200, response.get_data(as_text=True)
    db.session.expire_all()
    assert db.session.get(Announcement, announcement_id) is None
    assert db.session.get(PolicyVersion, version_id) is None
    assert db.session.get(PolicyTransition, transition_id) is None
    assert db.session.get(ClassEconomy, classroom.class_id) is None


@pytest.mark.parametrize('record', ['announcement', 'product', 'policy'])
def test_authors_cannot_be_borrowed_from_another_class(client, record):
    from app.services.announcement_service import create_class_announcement
    from app.services.store_service import publish_product, InvalidDefinition
    from app.services.insurance_policy_service import create_policy_version
    classroom = initialize('chemistry_p1', client.application)
    sibling = initialize('ap_csp_p3', client.application)
    with pytest.raises((ValueError, InvalidDefinition), match='teacher seat in this class'):
        with FEATContext('FEAT-TEST-SETUP', idempotency_key=f'seat-author:reject:{record}'):
            if record == 'announcement':
                create_class_announcement(created_by_seat_id=sibling.teacher_seat.id,
                    class_id=classroom.class_id, title='No', message='No',
                    priority='normal', is_active=True, expires_at=None)
            elif record == 'product':
                publish_product(class_id=classroom.class_id, actor_seat_id=sibling.teacher_seat.id,
                    definition={'name': 'No', 'price': Decimal('1.00'), 'item_type': 'delayed', 'economic_role': 'necessity'})
            else:
                create_policy_version(class_id=classroom.class_id, actor_seat_id=sibling.teacher_seat.id, payload={})


def test_migration_preserves_legacy_transfer_replay_without_principal_material(client):
    from app.services.ledger_transfer_service import create_transfer_pair
    classroom = initialize('chemistry_p1', client.application)
    with FEATContext('FEAT-TEST-SETUP', idempotency_key='migration:transfer'):
        debit, credit = create_transfer_pair(seat_id=classroom.students[0].seat.id,
            class_id=classroom.class_id, amount=Decimal('2.00'), from_account='checking',
            to_account='savings', withdraw_description='Transfer', deposit_description='Transfer')
        reservation_id = debit.command_reservation_id
    with db.engine.connect() as conn:
        transaction = conn.begin()
        try:
            conn.execute(sa.text('UPDATE ledger_command_reservation SET fingerprint_version=2 WHERE id=:id'), {'id': reservation_id})
            before = conn.execute(sa.text('SELECT replay_fingerprint FROM ledger_command_reservation WHERE id=:id'), {'id': reservation_id}).scalar()
            _migration(conn)._assert_replay_history_supported(conn)
            assert conn.execute(sa.text('SELECT replay_fingerprint FROM ledger_command_reservation WHERE id=:id'), {'id': reservation_id}).scalar() == before
        finally:
            transaction.rollback()


def test_removing_legacy_audit_principal_leaves_signed_history_unchanged(client):
    classroom = initialize('chemistry_p1', client.application)
    with FEATContext('FEAT-TEST-SETUP', idempotency_key='migration:audit'):
        create_pending_transaction(seat_id=classroom.students[0].seat.id,
            target_seat_id=classroom.students[0].seat.id, actor_seat_id=classroom.teacher_seat.id,
            class_id=classroom.class_id, mechanism='teacher', amount=Decimal('1.00'),
            account_type='checking', type='manual_payment', description='Audit migration test')
    db.session.rollback()  # release the ORM connection before exercising schema DDL
    with db.engine.connect() as conn:
        transaction = conn.begin()
        try:
            query = sa.text('SELECT id, event_hash, payload_digest, context_digest, hmac_signature FROM audit_events ORDER BY id')
            before = conn.execute(query).all()
            assert before
            # The legacy anchor was not a signed field. Simulate populated old metadata.
            conn.execute(sa.text('ALTER TABLE audit_events ADD COLUMN teacher_id INTEGER DEFAULT 123'))
            _migration(conn).upgrade()
            assert 'teacher_id' not in {c['name'] for c in sa.inspect(conn).get_columns('audit_events')}
            assert conn.execute(query).all() == before
        finally:
            transaction.rollback()


def test_operational_actor_logging_uses_scoped_seat_never_principal(app, caplog):
    from flask import g
    from types import SimpleNamespace
    from app.services import operational_event_service
    with app.test_request_context('/'):
        g.canonical_context = SimpleNamespace(user_id=918273, seat_id=456789, class_id='class-scope')
        operational_event_service.record(event_type='test', domain='test', class_id='class-scope')
        scoped = next(record for record in reversed(caplog.records) if record.msg == 'OPERATIONAL_EVENT %s').args
        assert scoped['actor_seat_id'] == 456789
        assert 'user_id' not in scoped and 918273 not in scoped.values()
        operational_event_service.record(event_type='test', domain='test', class_id=None)
        unscoped = next(record for record in reversed(caplog.records) if record.msg == 'OPERATIONAL_EVENT %s').args
        assert unscoped['actor_seat_id'] is None
