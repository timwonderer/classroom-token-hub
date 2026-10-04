"""DOM-OPS-002 §6.1: payroll creation → linkage → commit → immutability."""
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError
from flask_migrate import upgrade

from app.extensions import db
from app.feats.base import FEATContext, audit_protected
from app.models import AuditEvent, PayrollEvent
from app.utils.audit_verifier import PROTECTED_FIELDS_BY_TABLE, verify_row_lineage
from app.services.audit_service import LineageState
from tests.helpers.classroom_initializer import initialize


def _row(classroom):
    return PayrollEvent(
        class_id=classroom.class_id,
        actor_seat_id=classroom.teacher_seat.id,
        target_seat_id=classroom.students[0].seat.id,
        correlation_id=f'payroll:{uuid4()}', idempotency_key=f'payroll:{uuid4()}',
        mechanism='TEACHER', payroll_event_type='manual_credit',
        summary_json={'provenance': {'sources': [1, 2]}},
    )


def _attach(row):
    audit_protected('payroll_event', row, 'INSERT', PROTECTED_FIELDS_BY_TABLE['payroll_event'])


def _create(classroom):
    with FEATContext('FEAT-PROD-003', idempotency_key=f'create:{uuid4()}'):
        row = _row(classroom)
        db.session.add(row)
        db.session.flush()
        assert row.lineage_event_id is None
        _attach(row)
    return row


def test_creation_initialization_commit_verifies_and_registry_matches(app):
    classroom = initialize('chemistry_p1', app)
    row = _create(classroom)
    assert verify_row_lineage('payroll_event', row.id, row).state == LineageState.VERIFIED
    assert set(PROTECTED_FIELDS_BY_TABLE['payroll_event']) == {
        'id', 'class_id', 'payroll_cycle_id', 'actor_seat_id', 'target_seat_id',
        'correlation_id', 'idempotency_key', 'policy_uuid', 'mechanism',
        'payroll_event_type', 'recorded_at', 'summary_json',
    }


@pytest.mark.parametrize('field,value', [
    ('summary_json', {'sources': ['rewritten']}),
    ('lineage_event_id', 999999), ('lineage_token', '0' * 64), ('lineage_version', 99),
])
def test_committed_orm_business_and_linkage_are_permanently_immutable(app, field, value):
    row = _create(initialize('chemistry_p1', app))
    with pytest.raises(ValueError, match='immutable|initializes once'):
        with FEATContext('FEAT-PROD-003', idempotency_key=f'attack:{uuid4()}'):
            setattr(row, field, value)
            db.session.flush()


def test_missing_lineage_creation_cannot_commit(app):
    classroom = initialize('chemistry_p1', app)
    before = PayrollEvent.query.count()
    with pytest.raises(ValueError, match='requires complete audit lineage'):
        with FEATContext('FEAT-PROD-003', idempotency_key='missing-lineage'):
            db.session.add(_row(classroom))
            db.session.flush()
    assert PayrollEvent.query.count() == before


def test_linkage_replacement_before_commit_and_halfway_rollback(app):
    classroom = initialize('chemistry_p1', app)
    before = AuditEvent.query.count()
    with pytest.raises(ValueError, match='initializes once'):
        with FEATContext('FEAT-PROD-003', idempotency_key='replace-linkage'):
            row = _row(classroom)
            db.session.add(row)
            db.session.flush()
            _attach(row)
            db.session.flush()
            row.lineage_token = '0' * 64
            db.session.flush()
    assert PayrollEvent.query.count() == 0
    assert AuditEvent.query.count() == before
    assert verify_row_lineage('payroll_event', _create(classroom).id, PayrollEvent.query.first()).state == LineageState.VERIFIED


def test_insert_and_lineage_work_inside_savepoint_and_rollback_is_local(app):
    classroom = initialize('chemistry_p1', app)
    with FEATContext('FEAT-PROD-003', idempotency_key='nested-lineage'):
        with db.session.begin_nested():
            first = _row(classroom)
            db.session.add(first)
            db.session.flush()
            _attach(first)
            db.session.flush()
        with pytest.raises(RuntimeError, match='abort nested'):
            with db.session.begin_nested():
                abandoned = _row(classroom)
                db.session.add(abandoned)
                db.session.flush()
                _attach(abandoned)
                db.session.flush()
                raise RuntimeError('abort nested')
        second = _row(classroom)
        db.session.add(second)
        db.session.flush()
        _attach(second)
    assert PayrollEvent.query.count() == 2
    assert verify_row_lineage('payroll_event', first.id, first).state == LineageState.VERIFIED
    assert verify_row_lineage('payroll_event', second.id, second).state == LineageState.VERIFIED


def test_database_rejects_raw_unattested_insert_at_commit(app):
    classroom = initialize('chemistry_p1', app)
    db.session.rollback()
    with pytest.raises(DBAPIError, match='requires matching creation audit lineage'):
        with db.engine.begin() as conn:
            conn.execute(sa.text('''INSERT INTO payroll_event
                (class_id, actor_seat_id, target_seat_id, correlation_id,
                 idempotency_key, mechanism, payroll_event_type, recorded_at, summary_json)
                VALUES (:cid, :actor, :target, 'raw', 'raw', 'TEACHER', 'manual_credit', NOW(), '{}')'''),
                {'cid': classroom.class_id, 'actor': classroom.teacher_seat.id,
                 'target': classroom.students[0].seat.id})
    assert PayrollEvent.query.count() == 0


def test_database_rejects_committed_replacement_and_noop_laundering(app):
    row = _create(initialize('chemistry_p1', app))
    row_id = row.id
    db.session.rollback()
    for sql in (
        'UPDATE payroll_event SET lineage_token = :value WHERE id = :id',
        'UPDATE payroll_event SET summary_json = summary_json WHERE id = :id',
    ):
        with pytest.raises(DBAPIError, match='append-only'):
            with db.engine.begin() as conn:
                conn.execute(sa.text(sql), {'id': row_id, 'value': '0' * 64})


def test_historical_null_stays_unverified_and_late_attachment_is_denied(app, tmp_path):
    import json
    import os
    import subprocess
    import sys
    from tests.dom.prod.test_historical_v1_assessment import PREDECESSOR, REPOSITORY

    # Construct genuine predecessor data forward from its own schema. Walking
    # backwards from immutable evidence at head is forbidden, even in tests.
    source = tmp_path / 'predecessor'
    source.mkdir()
    archive = tmp_path / 'predecessor.tar'
    with archive.open('wb') as stream:
        subprocess.run(['git', 'archive', PREDECESSOR], cwd=REPOSITORY,
                       stdout=stream, check=True)
    subprocess.run(['tar', '-xf', str(archive), '-C', str(source)], check=True)
    environment = dict(os.environ, DATABASE_URL=os.environ['TEST_DATABASE_URL'],
                       PYTHONPATH=str(source))
    db.session.remove()
    created = subprocess.run([sys.executable, '-c', HISTORICAL_UNATTESTED_CREATION],
        cwd=source, env=environment, text=True, capture_output=True, timeout=90)
    assert created.returncode == 0, created.stdout[-3000:] + created.stderr[-3000:]
    row_id = json.loads(next(line.partition('=')[2] for line in created.stdout.splitlines()
                             if line.startswith('HISTORICAL_UNATTESTED=')))
    upgrade()
    old = db.session.get(PayrollEvent, row_id)
    assert old.lineage_event_id is None
    assert verify_row_lineage('payroll_event', row_id, old).state == LineageState.UNVERIFIED
    with pytest.raises(ValueError, match='initializes once'):
        with FEATContext('FEAT-PROD-003', idempotency_key='late-attachment'):
            _attach(old)
            db.session.flush()
    db.session.rollback()
    with pytest.raises(DBAPIError, match='append-only'):
        with db.engine.begin() as conn:
            conn.execute(sa.text('''UPDATE payroll_event SET lineage_event_id=1,
                lineage_token=:token, lineage_version=1 WHERE id=:id'''),
                {'id': row_id, 'token': '0' * 64})


def test_business_payload_cannot_change_even_before_initialization(app):
    classroom = initialize('chemistry_p1', app)
    with pytest.raises(ValueError, match='business fields are immutable'):
        with FEATContext('FEAT-PROD-003', idempotency_key='change-before-linkage'):
            row = _row(classroom)
            db.session.add(row)
            db.session.flush()
            row.summary_json = {'changed': True}
            _attach(row)
            db.session.flush()
    assert PayrollEvent.query.count() == 0


def test_partial_linkage_and_wrong_payload_event_fail_closed(app):
    from app.services.audit_service import emit_audit_event
    classroom = initialize('chemistry_p1', app)
    with pytest.raises(ValueError, match='initializes once'):
        with FEATContext('FEAT-PROD-003', idempotency_key='partial-linkage'):
            row = _row(classroom)
            db.session.add(row)
            db.session.flush()
            row.lineage_event_id = 1
            db.session.flush()
    with pytest.raises(ValueError, match='frozen payroll payload'):
        with FEATContext('FEAT-PROD-003', idempotency_key='wrong-payload'):
            row = _row(classroom)
            db.session.add(row)
            db.session.flush()
            wrong = emit_audit_event('payroll_event', str(row.id), 'INSERT',
                                     {'fake': 'payload'}, class_id=row.class_id)
            row.lineage_event_id = wrong.id
            row.lineage_token = wrong.hmac_signature
            row.lineage_version = wrong.signature_version
            db.session.flush()
    assert PayrollEvent.query.count() == 0


def test_productivity_insurance_can_create_only_manual_credit_lineage(app):
    from app.models import PayrollSettings
    classroom = initialize('chemistry_p1', app)
    with FEATContext('FEAT-STOR-003', idempotency_key='insurance-manual-credit'):
        row = _row(classroom)
        db.session.add(row)
        db.session.flush()
        _attach(row)
    assert verify_row_lineage('payroll_event', row.id, row).state == LineageState.VERIFIED
    policy = PayrollSettings.query.filter_by(class_id=classroom.class_id).first()
    with pytest.raises(ValueError, match='frozen payroll payload'):
        with FEATContext('FEAT-STOR-003', idempotency_key='insurance-cannot-create-worked-payroll'):
            denied = _row(classroom)
            denied.payroll_event_type = 'payroll'
            denied.policy_uuid = policy.policy_uuid
            db.session.add(denied)
            db.session.flush()
            _attach(denied)
            db.session.flush()
    assert PayrollEvent.query.count() == 1


def test_another_transaction_cannot_initialize_uncommitted_or_committed_row(app):
    classroom = initialize('chemistry_p1', app)
    with FEATContext('FEAT-PROD-003', idempotency_key='isolate-creating-transaction'):
        row = _row(classroom)
        db.session.add(row)
        db.session.flush()
        _attach(row)
        db.session.flush()
        row_id = row.id
        with db.engine.begin() as other:
            # The other connection sees no uncommitted INSERT despite its xmin
            # being in progress. It cannot borrow the initialization exception.
            result = other.execute(sa.text('''UPDATE payroll_event
                SET lineage_event_id=1, lineage_token=:token, lineage_version=1 WHERE id=:id'''),
                {'id': row_id, 'token': '0' * 64})
            assert result.rowcount == 0
    db.session.rollback()
    with pytest.raises(DBAPIError, match='append-only'):
        with db.engine.begin() as other:
            other.execute(sa.text('''UPDATE payroll_event
                SET lineage_event_id=1, lineage_token=:token, lineage_version=1 WHERE id=:id'''),
                {'id': row_id, 'token': '0' * 64})


def test_deferred_lineage_check_preserves_existing_seat_destruction(app):
    classroom = initialize('chemistry_p1', app)
    target_id = classroom.students[0].seat.id
    with FEATContext('FEAT-PROD-003', idempotency_key='create-then-universe-destruction'):
        row = _row(classroom)
        db.session.add(row)
        db.session.flush()
        _attach(row)
        db.session.flush()
        # The inherited database lifecycle guard permits the owning seat's
        # cascade; the deferred creation check must inspect the final row and
        # avoid reviving a row lawfully removed in its creating transaction.
        db.session.execute(sa.text('DELETE FROM seats WHERE id=:id'), {'id': target_id})
    assert PayrollEvent.query.count() == 0


def test_json_numeric_representation_is_frozen_before_linkage(app):
    classroom = initialize('chemistry_p1', app)
    with pytest.raises(ValueError, match='business fields are immutable'):
        with FEATContext('FEAT-PROD-003', idempotency_key='numeric-payload-rewrite'):
            row = _row(classroom)
            db.session.add(row)
            db.session.flush()
            row.summary_json = {'provenance': {'sources': [1.0, 2]}}
            _attach(row)
            db.session.flush()


HISTORICAL_UNATTESTED_CREATION = r"""
import json
from sqlalchemy import text
from flask_migrate import upgrade
from app import app, db
from tests.helpers.classroom_initializer import initialize
with app.app_context():
    assert 'test' in db.engine.url.database
    with db.engine.begin() as connection:
        connection.execute(text('DROP SCHEMA public CASCADE'))
        connection.execute(text('CREATE SCHEMA public'))
    upgrade(revision='a4b50fee84c3')
    classroom = initialize('chemistry_p1', app)
    with db.engine.begin() as connection:
        row_id = connection.execute(text('''INSERT INTO payroll_event
            (class_id, actor_seat_id, target_seat_id, correlation_id, idempotency_key,
             mechanism, payroll_event_type, recorded_at, summary_json)
            VALUES (:cid, :actor, :target, 'historic', 'historic', 'TEACHER',
                    'manual_credit', NOW(), '{}') RETURNING id'''),
            {'cid': classroom.class_id, 'actor': classroom.teacher_seat.id,
             'target': classroom.students[0].seat.id}).scalar_one()
    print('HISTORICAL_UNATTESTED=' + json.dumps(row_id))
"""
