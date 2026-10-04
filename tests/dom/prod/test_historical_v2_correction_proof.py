"""Actual checkpoint-runtime v2 creation, followed by forward-only migration."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from flask_migrate import upgrade
from itsdangerous import URLSafeSerializer

from app.extensions import db
from app.models import AuditEvent, AttendanceIntervalInvalidation, PayrollEvent, Transaction
from app.services.context_resolver import CanonicalContext
from app.services.attendance_invalidation_service import AttendanceCorrectionDenied
from app.feats.attendance_interval_invalidation_feat import preview_attendance_interval_invalidation, invalidate_attendance_interval
from app.utils.audit_verifier import verified_creation_evidence

CHECKPOINT = '81ea0fff5676c90a0bac673956737a7a139202e8'
REPOSITORY = Path(__file__).resolve().parents[3]

HISTORICAL_CREATION = r'''
import json, os
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from flask_migrate import upgrade
from app import app, db
from app.feats.base import FEATContext
from app.feats.prod import record_attendance_session, record_payroll_event
from app.models import AuditEvent, AttendanceReasonCode, Transaction
from app.services.context_resolver import CanonicalContext
from app.services.ledger_settlement_service import settle_balances
from app.services.ledger_correction_service import reverse_transaction
from tests.helpers.classroom_initializer import initialize

with app.app_context():
    # Only the dedicated, explicitly supplied disposable test database is valid.
    assert 'test' in db.engine.url.database
    with db.engine.begin() as connection:
        connection.execute(text('DROP SCHEMA public CASCADE'))
        connection.execute(text('CREATE SCHEMA public'))
    upgrade()
    classroom = initialize('chemistry_p1', app)
    ctx = CanonicalContext(classroom.teacher_user.id,classroom.class_id,classroom.teacher_seat.id,'teacher')
    target = classroom.students[0].seat.id
    instant = datetime(2026,8,1,18,tzinfo=timezone.utc)
    opening = record_attendance_session(ctx=ctx,target_seat_id=target,status='active',mechanism='teacher',
        idempotency_key='historical-open',reference_time_utc=instant).session
    closing = record_attendance_session(ctx=ctx,target_seat_id=target,status='inactive',mechanism='system',
        reason_code=AttendanceReasonCode.DONE_FOR_DAY,idempotency_key='historical-close',
        reference_time_utc=instant+timedelta(minutes=2)).session
    event = record_payroll_event(ctx=ctx,target_seat_id=target,payroll_event_type='payroll',
        correlation_id='corr_historical_credit',idempotency_key='historical-credit',mechanism='TEACHER',
        reference_time_utc=instant+timedelta(days=1)).payroll_event
    credit = Transaction.query.filter_by(idempotency_key='historical-credit').one()
    with FEATContext('FEAT-LED-003',idempotency_key='historical-settle'):
        settle_balances(target,ctx.class_id)
    if os.environ['HISTORICAL_PRIOR_RECOVERY']=='1':
        with FEATContext('FEAT-LED-002',idempotency_key='historical-reversal',correlation_id='corr_historical_recovery'):
            reverse_transaction(credit,description='Historical exact recovery',idempotency_key='historical-reversal',
                actor_seat_id=ctx.seat_id)
    audit = db.session.get(AuditEvent,credit.lineage_event_id)
    assert credit.lineage_version==audit.signature_version==2
    result = dict(class_id=ctx.class_id,user_id=ctx.user_id,actor=ctx.seat_id,target=target,
        opening=opening.id,closing=closing.id,event=event.id,credit=credit.id,
        lineage=[credit.lineage_event_id,credit.lineage_token,credit.lineage_version],
        audit=[audit.payload_digest,audit.event_hash,audit.signature_version],amount_cents=credit.amount_cents)
    print('HISTORICAL_RESULT='+json.dumps(result))
'''


@pytest.mark.parametrize('prior_recovery',[False,True])
def test_genuine_v2_credit_proof_survives_forward_migration_without_fabricated_attribution(app,tmp_path,prior_recovery):
    source = tmp_path/'checkpoint'
    source.mkdir()
    archive = tmp_path/'checkpoint.tar'
    with archive.open('wb') as output:
        subprocess.run(['git','archive',CHECKPOINT],cwd=REPOSITORY,stdout=output,check=True)
    subprocess.run(['tar','-xf',str(archive),'-C',str(source)],check=True)
    env = dict(os.environ, DATABASE_URL=os.environ['TEST_DATABASE_URL'],
        HISTORICAL_PRIOR_RECOVERY='1' if prior_recovery else '0', PYTHONPATH=str(source))
    db.session.remove()
    created = subprocess.run([sys.executable,'-c',HISTORICAL_CREATION],cwd=source,env=env,
        text=True,capture_output=True,timeout=90)
    assert created.returncode==0, created.stdout[-3000:]+created.stderr[-3000:]
    record = json.loads(next(line.partition('=')[2] for line in created.stdout.splitlines() if line.startswith('HISTORICAL_RESULT=')))
    upgrade()  # Forward from the real checkpoint e7 schema through f8/f9.
    credit = db.session.get(Transaction,record['credit'])
    audit = db.session.get(AuditEvent,credit.lineage_event_id)
    assert [credit.lineage_event_id,credit.lineage_token,credit.lineage_version]==record['lineage']
    assert [audit.payload_digest,audit.event_hash,audit.signature_version]==record['audit']
    assert credit.amount_cents==record['amount_cents']
    assert credit.compensation_origin_locator is credit.compensation_amount_cents is credit.correction_intent_locator is None
    evidence = verified_creation_evidence('ledger_transaction',credit,record['class_id'])
    assert evidence is not None and evidence.signature_version==2 and len(evidence.protected_fields)==16
    assert verified_creation_evidence('ledger_transaction',credit,record['class_id'],
        required_fields=('compensation_amount_cents',)) is None
    ctx = CanonicalContext(record['user_id'],record['class_id'],record['actor'],'teacher')
    args = dict(ctx=ctx,target_seat_id=record['target'],opening_event_id=record['opening'],
        closing_event_id=record['closing'],reason_code='INVALID_ATTENDANCE')
    if prior_recovery:
        before = (Transaction.query.count(),PayrollEvent.query.count(),AuditEvent.query.count())
        with pytest.raises(AttendanceCorrectionDenied,match='PROVENANCE_UNAVAILABLE'):
            preview_attendance_interval_invalidation(**args)
        with pytest.raises(AttendanceCorrectionDenied,match='PROVENANCE_UNAVAILABLE'):
            invalidate_attendance_interval(**args,idempotency_key='blocked-history',expected_preview_identity=URLSafeSerializer(app.secret_key, salt='attendance-correction-preview-v1').dumps({'version':1,'digest':'0'*64}))
        assert AttendanceIntervalInvalidation.query.count()==0
        assert before==(Transaction.query.count(),PayrollEvent.query.count(),AuditEvent.query.count())
    else:
        preview = preview_attendance_interval_invalidation(**args)
        assert preview.disposition=='PAID' and preview.public()['recovery_cents']==record['amount_cents']
        result = invalidate_attendance_interval(**args,idempotency_key='proven-v2-correction',expected_preview_identity=preview.identity)
        assert result['recovery_cents']==record['amount_cents']
        assert Transaction.query.filter(Transaction.compensation_amount_cents>0).one().lineage_version==3
    db.session.expire_all()
    assert [audit.payload_digest,audit.event_hash,audit.signature_version]==record['audit']
