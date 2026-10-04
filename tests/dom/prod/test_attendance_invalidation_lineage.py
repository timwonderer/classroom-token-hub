"""Independent gates for DOM-PROD-001 XI.4 / DOM-OPS-002 6.1."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from dataclasses import FrozenInstanceError

import pytest
import sqlalchemy as sa

from app.extensions import db
from app.feats.base import FEATContext, audit_protected
from app.feats.prod import record_attendance_session
from app.models import AttendanceIntervalInvalidation, AttendanceReasonCode, AuditEvent
from app.services.context_resolver import CanonicalContext
from app.services.attendance_invalidation_service import record_interval_invalidation
from app.utils.audit_verifier import PROTECTED_FIELDS_BY_TABLE, verified_creation_evidence
from tests.helpers.classroom_initializer import initialize


def _sources(app, count=1):
    classroom = initialize('chemistry_p1', app)
    ctx = CanonicalContext(classroom.teacher_user.id, classroom.class_id, classroom.teacher_seat.id, 'teacher')
    target = classroom.students[0].seat.id
    base = datetime(2026, 8, 1, 18, tzinfo=timezone.utc)
    pairs = []
    for index in range(count):
        instant = base + timedelta(days=index)
        opening = record_attendance_session(ctx=ctx, target_seat_id=target, status='active', mechanism='teacher',
            idempotency_key=f'guard-open:{index}', reference_time_utc=instant).session
        closing = record_attendance_session(ctx=ctx, target_seat_id=target, status='inactive', mechanism='system',
            reason_code=AttendanceReasonCode.DONE_FOR_DAY, idempotency_key=f'guard-close:{index}',
            reference_time_utc=instant + timedelta(minutes=2)).session
        pairs.append((opening.id, closing.id))
    return classroom, ctx, target, pairs


def _insert(ctx, target, pair):
    return record_interval_invalidation(ctx=ctx, target_seat_id=target,
        opening_event_id=pair[0], closing_event_id=pair[1], reason_code='INVALID_ATTENDANCE',
        idempotency_key=str(uuid4()), recorded_at=datetime.now(timezone.utc),
        receipt={'expected_preview_identity':'a'*64, 'fingerprint_version':1,
            'canonical_intent_digest':'b'*64, 'original_settlement_disposition':'UNPAID',
            'opaque_outcome_locators':{}})


def _attach(row):
    audit_protected('attendance_interval_invalidation', row, 'INSERT',
        PROTECTED_FIELDS_BY_TABLE['attendance_interval_invalidation'])


def _create(ctx, target, pair):
    with FEATContext('FEAT-PROD-005', idempotency_key=str(uuid4())):
        row = _insert(ctx, target, pair)
        _attach(row)
    return row


def test_creation_evidence_is_immutable_scoped_and_complete(app):
    classroom, ctx, target, pairs = _sources(app)
    row = _create(ctx, target, pairs[0])
    evidence = verified_creation_evidence('attendance_interval_invalidation', row, classroom.class_id,
        required_fields=('receipt_json','opening_event_id'))
    assert evidence.row_pk == str(row.id)
    assert len(evidence.protected_fields) == 11
    assert isinstance(dict(evidence.protected_values)['receipt_json'], tuple)
    with pytest.raises(FrozenInstanceError):
        evidence.class_id = 'foreign'
    assert verified_creation_evidence('attendance_interval_invalidation', row, 'foreign') is None
    assert verified_creation_evidence('attendance_interval_invalidation', row, classroom.class_id,
        required_fields=('invented_amount',)) is None


@pytest.mark.parametrize('field,value', [('receipt_json',{}),('reason_code','NON_WORK_ACTIVITY'),
    ('lineage_event_id',999999),('lineage_token','0'*64),('lineage_version',99)])
def test_committed_business_and_linkage_cannot_change(app, field, value):
    _, ctx, target, pairs = _sources(app)
    row = _create(ctx, target, pairs[0])
    with pytest.raises(ValueError, match='immutable|once'):
        with FEATContext('FEAT-PROD-005', idempotency_key=str(uuid4())):
            setattr(row, field, value)
            db.session.flush()


def test_missing_creation_lineage_rolls_back(app):
    _, ctx, target, pairs = _sources(app)
    with pytest.raises(ValueError, match='complete creation audit lineage'):
        with FEATContext('FEAT-PROD-005', idempotency_key=str(uuid4())):
            _insert(ctx, target, pairs[0])
    assert AttendanceIntervalInvalidation.query.count() == 0


def test_partial_linkage_and_business_rewrite_before_attachment_are_denied(app):
    _, ctx, target, pairs = _sources(app)
    for attack in ('partial','payload'):
        with pytest.raises(ValueError, match='once|immutable'):
            with FEATContext('FEAT-PROD-005', idempotency_key=str(uuid4())):
                row = _insert(ctx, target, pairs[0])
                if attack == 'partial':
                    row.lineage_event_id = 123
                else:
                    row.receipt_json = dict(row.receipt_json, fingerprint_version=1.0)
                db.session.flush()
    assert AttendanceIntervalInvalidation.query.count() == 0


def test_wrong_payload_and_linkage_replacement_roll_back_audit(app):
    _, ctx, target, pairs = _sources(app)
    before = AuditEvent.query.count()
    for attack in ('payload','replacement'):
        with pytest.raises(ValueError, match='frozen receipt|once'):
            with FEATContext('FEAT-PROD-005', idempotency_key=str(uuid4())):
                row = _insert(ctx, target, pairs[0])
                if attack == 'payload':
                    audit_protected('attendance_interval_invalidation', row, 'INSERT', ['id'])
                else:
                    _attach(row)
                    db.session.flush()
                    row.lineage_token = '0'*64
                db.session.flush()
    assert AttendanceIntervalInvalidation.query.count() == 0
    assert AuditEvent.query.count() == before


def test_nested_creation_rollback_preserves_sibling_evidence(app):
    classroom, ctx, target, pairs = _sources(app, count=3)
    with FEATContext('FEAT-PROD-005', idempotency_key=str(uuid4())):
        with db.session.begin_nested():
            first = _insert(ctx, target, pairs[0]); _attach(first); db.session.flush()
        with pytest.raises(RuntimeError, match='abort nested'):
            with db.session.begin_nested():
                abandoned = _insert(ctx, target, pairs[1]); _attach(abandoned); db.session.flush()
                raise RuntimeError('abort nested')
        second = _insert(ctx, target, pairs[2]); _attach(second)
    assert AttendanceIntervalInvalidation.query.count() == 2
    assert verified_creation_evidence('attendance_interval_invalidation', first, classroom.class_id)
    assert verified_creation_evidence('attendance_interval_invalidation', second, classroom.class_id)


def test_raw_unattested_insert_cannot_commit(app):
    classroom, ctx, target, pairs = _sources(app)
    params={'cid':classroom.class_id,'actor':ctx.seat_id,'target':target,'opening':pairs[0][0],'closing':pairs[0][1]}
    db.session.rollback()
    with pytest.raises(sa.exc.DBAPIError, match='requires matching creation lineage'):
        with db.engine.begin() as conn:
            conn.execute(sa.text("""INSERT INTO attendance_interval_invalidation
                (class_id,actor_seat_id,target_seat_id,opening_event_id,closing_event_id,recorded_at,
                reason_code,idempotency_key,correlation_id,receipt_json)
                VALUES (:cid,:actor,:target,:opening,:closing,NOW(),'INVALID_ATTENDANCE','raw','raw','{}')"""),params)
    assert AttendanceIntervalInvalidation.query.count() == 0


def test_database_blocks_committed_noop_laundering_and_replacement(app):
    _, ctx, target, pairs = _sources(app)
    row = _create(ctx, target, pairs[0]); row_id=row.id
    db.session.rollback()
    for assignment in ('receipt_json=receipt_json',"lineage_token='replacement'"):
        with pytest.raises(sa.exc.DBAPIError, match='immutable'):
            with db.engine.begin() as conn:
                conn.execute(sa.text(f'UPDATE attendance_interval_invalidation SET {assignment} WHERE id=:id'),{'id':row_id})


def test_surviving_target_prevents_direct_delete_and_target_removal_cascades(app):
    _, ctx, target, pairs = _sources(app)
    row = _create(ctx, target, pairs[0]); row_id=row.id
    db.session.rollback()
    with pytest.raises(sa.exc.DBAPIError, match='surviving target'):
        with db.engine.begin() as conn:
            conn.execute(sa.text('DELETE FROM attendance_interval_invalidation WHERE id=:id'),{'id':row_id})
    with FEATContext('FEAT-CLASS-006', idempotency_key=str(uuid4())):
        db.session.execute(sa.text('DELETE FROM seats WHERE id=:id'),{'id':target})
    assert AttendanceIntervalInvalidation.query.count() == 0


def test_deferred_creation_check_permits_same_transaction_target_destruction(app):
    _, ctx, target, pairs = _sources(app)
    with FEATContext('FEAT-PROD-005', idempotency_key=str(uuid4())):
        row = _insert(ctx,target,pairs[0]); _attach(row); db.session.flush()
        db.session.execute(sa.text('DELETE FROM seats WHERE id=:id'),{'id':target})
    assert AttendanceIntervalInvalidation.query.count() == 0


def test_class_destruction_removes_business_evidence_under_existing_lifecycle(app):
    from app.services.teacher_destruction import _destroy_class_scope_rows
    classroom, ctx, target, pairs = _sources(app)
    _create(ctx, target, pairs[0])
    with FEATContext('FEAT-CLASS-006', idempotency_key=str(uuid4())):
        _destroy_class_scope_rows(class_id=classroom.class_id, canonical_context=ctx)
    assert AttendanceIntervalInvalidation.query.count() == 0


def test_actor_and_audit_locators_cannot_own_surviving_target_records():
    columns=AttendanceIntervalInvalidation.__table__.columns
    assert not columns.actor_seat_id.foreign_keys
    assert all(not columns[field].foreign_keys for field in ('lineage_event_id','lineage_token','lineage_version'))
    assert next(iter(columns.target_seat_id.foreign_keys)).ondelete == 'CASCADE'


def test_ledger_versioned_registry_preserves_exact_emitter_payloads():
    from app.utils.audit_verifier import LEDGER_FIELDS_BY_VERSION
    from app.services.ledger_posting_service import _TRANSACTION_AUDIT_FIELDS_V2, _TRANSACTION_AUDIT_FIELDS
    version_two = (
        "id", "class_id", "actor_seat_id", "target_seat_id", "mechanism", "amount_cents",
        "timestamp", "account_type", "description", "correlation_id", "feat_code",
        "idempotency_key", "policy_id", "type", "posting_sequence", "command_reservation_id",
    )
    assert LEDGER_FIELDS_BY_VERSION[2] == version_two == tuple(_TRANSACTION_AUDIT_FIELDS_V2)
    assert LEDGER_FIELDS_BY_VERSION[3] == version_two + (
        "compensation_origin_locator", "compensation_amount_cents", "correction_intent_locator",
    ) == tuple(_TRANSACTION_AUDIT_FIELDS)
    assert len(LEDGER_FIELDS_BY_VERSION[2]) == 16 and len(LEDGER_FIELDS_BY_VERSION[3]) == 19
    assert 'status' not in LEDGER_FIELDS_BY_VERSION[2]
