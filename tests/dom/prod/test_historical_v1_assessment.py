"""Actual ad957 runtime produces v1 evidence; no synthetic version overrides."""
import json
import os
from pathlib import Path
import subprocess
import sys

from flask_migrate import upgrade
from app.extensions import db
from app.models import AuditEvent,Transaction
from app.services.context_resolver import CanonicalContext
from app.feats.historical_attendance_proof_feat import assess_historical_attendance_proof
from app.utils.audit_verifier import verified_creation_evidence

PREDECESSOR='ad9574334d72fd92cc93402e851ab0ebc22aaad9'
REPOSITORY=Path(__file__).resolve().parents[3]

CREATION=r'''
import json
from datetime import datetime,timedelta,timezone
from sqlalchemy import text
from flask_migrate import upgrade
from app import app,db
from app.feats.base import FEATContext
from app.feats.prod import record_attendance_session,record_payroll_event
from app.models import AuditEvent,AttendanceReasonCode,Transaction
from app.services.context_resolver import CanonicalContext
from app.services.ledger_settlement_service import settle_balances
from tests.helpers.classroom_initializer import initialize
with app.app_context():
    assert 'test' in db.engine.url.database
    with db.engine.begin() as connection:
        connection.execute(text('DROP SCHEMA public CASCADE'))
        connection.execute(text('CREATE SCHEMA public'))
    upgrade()
    classroom=initialize('chemistry_p1',app)
    ctx=CanonicalContext(classroom.teacher_user.id,classroom.class_id,classroom.teacher_seat.id,'teacher')
    target=classroom.students[0].seat.id
    at=datetime(2026,8,1,18,tzinfo=timezone.utc)
    opening=record_attendance_session(ctx=ctx,target_seat_id=target,status='active',mechanism='teacher',idempotency_key='v1-open',reference_time_utc=at).session
    closing=record_attendance_session(ctx=ctx,target_seat_id=target,status='inactive',mechanism='system',reason_code=AttendanceReasonCode.DONE_FOR_DAY,idempotency_key='v1-close',reference_time_utc=at+timedelta(minutes=2)).session
    event=record_payroll_event(ctx=ctx,target_seat_id=target,payroll_event_type='payroll',correlation_id='corr_v1-credit',idempotency_key='v1-credit',mechanism='TEACHER',reference_time_utc=at+timedelta(days=1)).payroll_event
    credit=Transaction.query.filter_by(idempotency_key='v1-credit').one()
    with FEATContext('FEAT-LED-003',idempotency_key='v1-settle'):
        settle_balances(target,ctx.class_id)
    audit=db.session.get(AuditEvent,credit.lineage_event_id)
    assert credit.lineage_version==audit.signature_version==1
    result=dict(class_id=ctx.class_id,user_id=ctx.user_id,actor=ctx.seat_id,target=target,event=event.id,credit=credit.id,
        source=[opening.id,closing.id],amount=str(credit.amount),sequence=credit.posting_sequence,
        lineage=[credit.lineage_event_id,credit.lineage_token,credit.lineage_version],
        audit=[audit.payload_digest,audit.event_hash,audit.signature_version])
    print('GENUINE_V1='+json.dumps(result))
'''


def test_genuine_v1_envelope_survives_forward_migration_but_never_admits_paid_correction(app,tmp_path):
    source=tmp_path/'predecessor';source.mkdir()
    archive=tmp_path/'predecessor.tar'
    with archive.open('wb') as stream:
        subprocess.run(['git','archive',PREDECESSOR],cwd=REPOSITORY,stdout=stream,check=True)
    subprocess.run(['tar','-xf',str(archive),'-C',str(source)],check=True)
    environment=dict(os.environ,DATABASE_URL=os.environ['TEST_DATABASE_URL'],PYTHONPATH=str(source))
    db.session.remove()
    created=subprocess.run([sys.executable,'-c',CREATION],cwd=source,env=environment,
        text=True,capture_output=True,timeout=90)
    assert created.returncode==0,created.stdout[-3000:]+created.stderr[-3000:]
    record=json.loads(next(line.partition('=')[2] for line in created.stdout.splitlines() if line.startswith('GENUINE_V1=')))
    upgrade()
    credit=db.session.get(Transaction,record['credit']);audit=db.session.get(AuditEvent,credit.lineage_event_id)
    assert [credit.lineage_event_id,credit.lineage_token,credit.lineage_version]==record['lineage']
    assert [audit.payload_digest,audit.event_hash,audit.signature_version]==record['audit']
    assert str(credit.amount)==record['amount'] and credit.posting_sequence==record['sequence']
    assert verified_creation_evidence('ledger_transaction',credit,record['class_id']) is None
    ctx=CanonicalContext(record['user_id'],record['class_id'],record['actor'],'teacher')
    result=assess_historical_attendance_proof(ctx=ctx,target_seat_id=record['target'])
    assert result.business.source_ids==tuple(record['source'])
    assert result.business.events[0].rule.record_writer_attribution=='UNAVAILABLE'
    assert result.current_execution_eligibility=='BLOCKED_DIAGNOSTIC_ONLY'
    diagnostic=next(d for d in result.audit_coverage if d.row_pk==str(credit.id))
    assert diagnostic.envelope_status=='AUTHENTICATED' and diagnostic.chain_status=='COMPLETE'
    assert len(diagnostic.candidate_protected_fields)==11 and not diagnostic.confirmed_protected_fields
    monetary=dict(result.money)[record['event']]
    assert monetary.arithmetic_comparison=='MATCH' and monetary.recovered_cents is None
    assert [audit.payload_digest,audit.event_hash,audit.signature_version]==record['audit']
