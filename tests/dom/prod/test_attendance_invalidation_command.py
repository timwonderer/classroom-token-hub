"""FEAT-PROD-005 atomic command and signed pure preview acceptance."""
from uuid import uuid4
import pytest
from app.extensions import db
from app.models import AttendanceIntervalInvalidation, AttendanceSession, AttendanceReasonCode, AuditEvent, PayrollEvent, Transaction
from app.feats.attendance_interval_invalidation_feat import preview_attendance_interval_invalidation as preview, invalidate_attendance_interval as execute
from app.services.attendance_invalidation_service import AttendanceCorrectionDenied
from app.services.attendance_service import calculate_seat_payroll_intervals
from tests.dom.prod.test_attendance_invalidation_lineage import _sources


def _args(ctx,target,pair,reason='INVALID_ATTENDANCE'):
    return dict(ctx=ctx,target_seat_id=target,opening_event_id=pair[0],closing_event_id=pair[1],reason_code=reason)


def _accept(args,key=None,identity=None):
    return execute(**args,idempotency_key=key or str(uuid4()),expected_preview_identity=identity or preview(**args).identity)


@pytest.mark.parametrize('reason',['INVALID_ATTENDANCE','NON_WORK_ACTIVITY','DUPLICATE_PARTICIPATION'])
def test_unpaid_terminal_command_keeps_scans_excludes_work_and_replays(app,reason):
    _,ctx,target,pairs=_sources(app)
    args=_args(ctx,target,pairs[0],reason)
    before=[(x.id,x.status,x.timestamp,x.reason_code) for x in AttendanceSession.query.all()]
    key=str(uuid4()); identity=preview(**args).identity
    result=_accept(args,key,identity)
    assert result['disposition']=='UNPAID' and result['recovery_cents']==0
    assert [(x.id,x.status,x.timestamp,x.reason_code) for x in AttendanceSession.query.all()]==before
    assert not calculate_seat_payroll_intervals(target,ctx.class_id,ctx=ctx).payable
    assert PayrollEvent.query.count()==0 and Transaction.query.count()==0
    assert _accept(args,key,identity)['replayed']
    assert AttendanceIntervalInvalidation.query.count()==1
    with pytest.raises(AttendanceCorrectionDenied,match='ALREADY_INVALIDATED'):
        _accept(args,identity=identity)
    with pytest.raises(AttendanceCorrectionDenied,match='REPLAY_MISMATCH'):
        _accept(dict(args,reason_code='NON_WORK_ACTIVITY' if reason!='NON_WORK_ACTIVITY' else 'INVALID_ATTENDANCE'),key,identity)


def test_preview_is_signed_stable_and_read_only(app,monkeypatch):
    _,ctx,target,pairs=_sources(app)
    args=_args(ctx,target,pairs[0])
    counts=[model.query.count() for model in (AttendanceSession,AttendanceIntervalInvalidation,AuditEvent,PayrollEvent,Transaction)]
    monkeypatch.setattr(db.session,'flush',lambda *a,**k:pytest.fail('preview flushed'))
    monkeypatch.setattr(db.session,'commit',lambda *a,**k:pytest.fail('preview committed'))
    first=preview(**args); second=preview(**args)
    assert first.identity==second.identity and len(first.identity)>64
    assert counts==[model.query.count() for model in (AttendanceSession,AttendanceIntervalInvalidation,AuditEvent,PayrollEvent,Transaction)]


def test_tampered_signed_preview_creates_nothing(app):
    _,ctx,target,pairs=_sources(app)
    args=_args(ctx,target,pairs[0]); identity=preview(**args).identity
    with pytest.raises(AttendanceCorrectionDenied,match='PREVIEW_CHANGED'):
        _accept(args,identity=identity+'tampered')
    assert AttendanceIntervalInvalidation.query.count()==0


@pytest.mark.parametrize('change',['reason','pair'])
def test_signed_preview_binds_request(app,change):
    _,ctx,target,pairs=_sources(app,count=2)
    args=_args(ctx,target,pairs[0]); identity=preview(**args).identity
    changed=dict(args,reason_code='NON_WORK_ACTIVITY') if change=='reason' else _args(ctx,target,pairs[1])
    with pytest.raises(AttendanceCorrectionDenied,match='PREVIEW_CHANGED'):
        _accept(changed,identity=identity)
    assert AttendanceIntervalInvalidation.query.count()==0


def test_open_or_noncanonical_pair_fails_closed(app):
    _,ctx,target,pairs=_sources(app,count=2)
    for pair in ((pairs[0][0],None),(pairs[0][0],pairs[1][1])):
        with pytest.raises(AttendanceCorrectionDenied,match='INCOMPLETE_INTERVAL'):
            preview(**_args(ctx,target,pair))


def test_foreign_target_fails_before_evidence(app):
    classroom,ctx,target,pairs=_sources(app)
    with pytest.raises(AttendanceCorrectionDenied,match='UNAUTHORIZED_SCOPE'):
        preview(**_args(ctx,999999,pairs[0]))


def test_failure_after_decision_insert_rolls_back_decision_and_audit(app,monkeypatch):
    _,ctx,target,pairs=_sources(app)
    args=_args(ctx,target,pairs[0]); identity=preview(**args).identity
    before=AuditEvent.query.count()
    import app.feats.attendance_interval_invalidation_feat as command
    def fail(*args,**kwargs):raise RuntimeError('injected audit failure')
    monkeypatch.setattr(command,'audit_protected',fail)
    with pytest.raises(RuntimeError,match='injected'):_accept(args,identity=identity)
    assert AttendanceIntervalInvalidation.query.count()==0 and AuditEvent.query.count()==before


def _paid_sources(app,posted=True):
    from datetime import datetime, timezone
    from app.feats.base import FEATContext
    from app.feats.prod import record_payroll_event
    from app.services.ledger_settlement_service import settle_balances
    from tests.helpers.ledger import record_ledger_fixture
    classroom,ctx,target,pairs=_sources(app,count=2)
    with FEATContext('FEAT-LED-001',idempotency_key='correction-seed'):
        record_ledger_fixture(seat_id=target,class_id=ctx.class_id,amount=0,posted=True)
    event=record_payroll_event(ctx=ctx,target_seat_id=target,payroll_event_type='payroll',
        correlation_id='corr_correction-original',idempotency_key='correction-original',mechanism='TEACHER',
        reference_time_utc=datetime(2026,8,3,18,tzinfo=timezone.utc)).payroll_event
    if posted:
        with FEATContext('FEAT-LED-003',idempotency_key='correction-original-settle'):
            settle_balances(target,ctx.class_id)
    return classroom,ctx,target,pairs,event


def test_paid_interval_then_residual_recovers_exact_original_no_double_recovery(app):
    from app.feats.attendance_interval_invalidation_feat import preview_payroll_recovery,recover_payroll_payment
    _,ctx,target,pairs,event=_paid_sources(app)
    credit=Transaction.query.filter_by(class_id=ctx.class_id,idempotency_key='correction-original').one()
    original=(credit.amount,credit.lineage_token,event.summary_json.copy())
    args=_args(ctx,target,pairs[0]); first=preview(**args)
    assert first.disposition=='PAID' and first.public()['recovery_cents']>0
    _accept(args,identity=first.identity)
    residual=preview_payroll_recovery(ctx=ctx,payroll_event_id=event.id)
    assert residual.disposition=='RESIDUAL'
    result=recover_payroll_payment(ctx=ctx,payroll_event_id=event.id,idempotency_key='correction-residual',expected_preview_identity=residual.identity)
    assert first.public()['recovery_cents']+result['recovery_cents']==credit.amount_cents
    after=preview(**_args(ctx,target,pairs[1]))
    assert after.disposition=='RECOVERED' and after.plan is None
    _accept(_args(ctx,target,pairs[1]),identity=after.identity)
    assert (credit.amount,credit.lineage_token,event.summary_json)==original
    assert sum(x.compensation_amount_cents or 0 for x in Transaction.query.filter_by(class_id=ctx.class_id).all())==credit.amount_cents
    assert recover_payroll_payment(ctx=ctx,payroll_event_id=event.id,idempotency_key='correction-residual',expected_preview_identity=residual.identity)['replayed']


def test_pending_original_blocks_paid_invalidation(app):
    _,ctx,target,pairs,event=_paid_sources(app,posted=False)
    with pytest.raises(AttendanceCorrectionDenied,match='PAYROLL_PENDING'):
        preview(**_args(ctx,target,pairs[0]))
    assert AttendanceIntervalInvalidation.query.count()==0


def test_full_recovery_then_invalidate_does_not_recover_twice(app):
    from app.feats.attendance_interval_invalidation_feat import preview_payroll_recovery,recover_payroll_payment
    _,ctx,target,pairs,event=_paid_sources(app)
    full=preview_payroll_recovery(ctx=ctx,payroll_event_id=event.id)
    assert full.disposition=='EXACT_REVERSAL'
    recover_payroll_payment(ctx=ctx,payroll_event_id=event.id,idempotency_key='correction-full',expected_preview_identity=full.identity)
    before=Transaction.query.count()
    args=_args(ctx,target,pairs[0]); p=preview(**args)
    assert p.disposition=='RECOVERED'
    _accept(args,identity=p.identity)
    assert Transaction.query.count()==before


def test_paid_preview_changes_after_new_balance_effect_and_rollback_is_clean(app):
    from app.feats.base import FEATContext
    from tests.helpers.ledger import record_ledger_fixture
    _,ctx,target,pairs,event=_paid_sources(app)
    args=_args(ctx,target,pairs[0]); identity=preview(**args).identity
    with FEATContext('FEAT-LED-001',idempotency_key='changed-balance'):
        record_ledger_fixture(seat_id=target,class_id=ctx.class_id,amount=1,posted=False)
    before=Transaction.query.count()
    with pytest.raises(AttendanceCorrectionDenied,match='PREVIEW_CHANGED'):_accept(args,identity=identity)
    assert Transaction.query.count()==before and AttendanceIntervalInvalidation.query.count()==0


@pytest.mark.parametrize('phase',['reservation','business','audit','commit'])
def test_paid_faults_roll_back_effects_reservation_business_and_audit(app,monkeypatch,phase):
    _,ctx,target,pairs,event=_paid_sources(app)
    args=_args(ctx,target,pairs[0]); identity=preview(**args).identity
    from app.models import LedgerCommandReservation
    models=(Transaction,PayrollEvent,AttendanceIntervalInvalidation,AuditEvent,LedgerCommandReservation)
    counts=[model.query.count() for model in models]
    from copy import deepcopy
    credit=Transaction.query.filter_by(class_id=ctx.class_id,idempotency_key='correction-original').one()
    original=(credit.amount,credit.lineage_token,event.lineage_token,deepcopy(event.summary_json))
    import app.feats.attendance_interval_invalidation_feat as command
    def fail(*a,**k):raise RuntimeError('injected acceptance failure')
    from sqlalchemy import event as sa_event
    if phase=='reservation':sa_event.listen(LedgerCommandReservation,'before_insert',fail)
    elif phase=='business':monkeypatch.setattr(command,'record_interval_invalidation',fail)
    elif phase=='audit':monkeypatch.setattr(command,'audit_protected',fail)
    else:
        from sqlalchemy import event as sa_event
        sa_event.listen(db.session(), 'before_commit', fail, once=True)
    try:
        with pytest.raises(RuntimeError,match='injected'):_accept(args,identity=identity)
    finally:
        if phase=='reservation':sa_event.remove(LedgerCommandReservation,'before_insert',fail)
    assert [model.query.count() for model in models]==counts
    assert (credit.amount,credit.lineage_token,event.lineage_token,event.summary_json)==original
    from app.utils.audit_verifier import verify_record_creation_lineage
    assert verify_record_creation_lineage('ledger_transaction',credit,ctx.class_id)
    assert verify_record_creation_lineage('payroll_event',event,ctx.class_id)


def test_two_paid_interval_corrections_preserve_total_and_duplicate_cannot_recover(app):
    _,ctx,target,pairs,event=_paid_sources(app)
    credit=Transaction.query.filter_by(class_id=ctx.class_id,idempotency_key='correction-original').one()
    total=0
    for pair in pairs:
        args=_args(ctx,target,pair); p=preview(**args); total+=p.public()['recovery_cents']
        _accept(args,identity=p.identity)
        with pytest.raises(AttendanceCorrectionDenied,match='ALREADY_INVALIDATED'):_accept(args,identity=p.identity)
    assert total==credit.amount_cents


def _cent_payment(app,seconds):
    from datetime import datetime,timedelta,timezone
    from decimal import Decimal
    from tests.helpers.classroom_initializer import initialize
    from tests.helpers.class_domain import put_payroll_setting_in_force
    from app.services.context_resolver import CanonicalContext
    from app.feats.prod import record_attendance_session,record_payroll_event
    from app.feats.base import FEATContext
    from app.services.ledger_settlement_service import settle_balances
    from tests.helpers.ledger import record_ledger_fixture
    classroom=initialize('chemistry_p1',app);ctx=CanonicalContext(classroom.teacher_user.id,classroom.class_id,classroom.teacher_seat.id,'teacher');target=classroom.students[0].seat.id
    from unittest.mock import patch
    base=datetime.now(timezone.utc)-timedelta(days=3)
    with patch('app.utils.canonical_temporal_resolver.utc_now',return_value=base-timedelta(days=1)):
        put_payroll_setting_in_force(ctx.class_id,pay_rate=Decimal('0.01'))
    pairs=[]
    for index,duration in enumerate(seconds):
        start=base+timedelta(days=index)
        opening=record_attendance_session(ctx=ctx,target_seat_id=target,status='active',mechanism='teacher',idempotency_key=f'cent:open:{index}',reference_time_utc=start).session
        closing=record_attendance_session(ctx=ctx,target_seat_id=target,status='inactive',mechanism='teacher',reason_code=AttendanceReasonCode.DONE_FOR_DAY,idempotency_key=f'cent:close:{index}',reference_time_utc=start+timedelta(seconds=duration)).session
        pairs.append((opening.id,closing.id))
    with FEATContext('FEAT-LED-001',idempotency_key='cent-seed'):
        record_ledger_fixture(seat_id=target,class_id=ctx.class_id,amount=0,posted=True)
    event=record_payroll_event(ctx=ctx,target_seat_id=target,payroll_event_type='payroll',correlation_id='corr_cent-payment',idempotency_key='cent-payment',mechanism='TEACHER',reference_time_utc=base+timedelta(days=len(seconds)-1,hours=1)).payroll_event
    with FEATContext('FEAT-LED-003',idempotency_key='cent-settle'):settle_balances(target,ctx.class_id)
    return ctx,target,pairs,event


def test_three_equal_intervals_allocate_2_2_1_cents_and_preserve_recovery_total(app):
    ctx,target,pairs,event=_cent_payment(app,[100,100,100]);amounts=[]
    for pair in pairs:
        args=_args(ctx,target,pair);p=preview(**args);amounts.append(p.public()['recovery_cents']);_accept(args,identity=p.identity)
    assert amounts==[2,2,1]
    assert sum(x.compensation_amount_cents or 0 for x in Transaction.query.filter_by(class_id=ctx.class_id).all())==5


def test_verified_zero_cent_interval_invalidates_without_any_money_effect(app):
    ctx,target,pairs,event=_cent_payment(app,[1,120]);args=_args(ctx,target,pairs[0]);p=preview(**args)
    assert p.disposition=='ZERO_CENT' and p.plan is None
    before=(Transaction.query.count(),PayrollEvent.query.count());_accept(args,identity=p.identity)
    assert before==(Transaction.query.count(),PayrollEvent.query.count())


@pytest.mark.parametrize('summary',[{}, {'allocation_version':1,'pricing':[{'intervals':[]}]}])
def test_historical_unprovable_membership_and_pricing_block_atomic_action(app,summary):
    from datetime import datetime,timezone
    from app.feats.base import FEATContext,audit_protected
    from app.utils.audit_verifier import PROTECTED_FIELDS_BY_TABLE
    from app.services.payroll.settings import first_payroll_setting
    _,ctx,target,pairs=_sources(app)
    with FEATContext('FEAT-PROD-003',idempotency_key='historical-unproven'):
        event=PayrollEvent(class_id=ctx.class_id,target_seat_id=target,actor_seat_id=ctx.seat_id,
            correlation_id='corr_historical-unproven',idempotency_key='historical-unproven',
            policy_uuid=first_payroll_setting(ctx.class_id).policy_uuid,mechanism='TEACHER',payroll_event_type='payroll',
            recorded_at=datetime(2026,8,3,18,tzinfo=timezone.utc),summary_json=summary)
        db.session.add(event);db.session.flush();audit_protected('payroll_event',event,'INSERT',PROTECTED_FIELDS_BY_TABLE['payroll_event'])
    before=AttendanceSession.query.count()
    with pytest.raises(AttendanceCorrectionDenied,match='PROVENANCE_UNAVAILABLE'):preview(**_args(ctx,target,pairs[0]))
    assert AttendanceIntervalInvalidation.query.count()==0 and AttendanceSession.query.count()==before


def test_unrelated_same_class_audit_advance_does_not_change_preview(app):
    from datetime import datetime,timezone
    from app.feats.prod import record_attendance_session
    classroom,ctx,target,pairs,event=_paid_sources(app)
    args=_args(ctx,target,pairs[0]);identity=preview(**args).identity
    record_attendance_session(ctx=ctx,target_seat_id=classroom.students[1].seat.id,status='active',
        mechanism='teacher',idempotency_key='unrelated-audit-advance',reference_time_utc=datetime(2026,8,5,18,tzinfo=timezone.utc))
    assert preview(**args).identity==identity


def test_applicable_banking_change_invalidates_signed_preview(app):
    from app.feats.base import FEATContext
    from app.models import EconomicEngine
    from datetime import datetime,timezone
    _,ctx,target,pairs,event=_paid_sources(app)
    args=_args(ctx,target,pairs[0]);identity=preview(**args).identity
    current=EconomicEngine.query.filter_by(class_id=ctx.class_id).order_by(EconomicEngine.created_at.desc()).first()
    with FEATContext('FEAT-SETTINGS-001',idempotency_key='changed-protection'):
        instant=datetime.now(timezone.utc)
        new=EconomicEngine(class_id=ctx.class_id,economic_version_id='preview-changed-protection',
            previous_version_id=current.economic_version_id,economy_policy_mode=current.economy_policy_mode,
            overdraft_protection_enabled=not bool(current.overdraft_protection_enabled),created_at=instant,effective_at=instant)
        db.session.add(new);db.session.flush()
    with pytest.raises(AttendanceCorrectionDenied,match='PREVIEW_CHANGED'):_accept(args,identity=identity)
    assert AttendanceIntervalInvalidation.query.count()==0


def test_new_payroll_freezes_canonical_feat_correlation_shared_with_credit(app):
    from datetime import datetime,timezone
    from app.feats.prod import record_payroll_event
    _,ctx,target,pairs=_sources(app)
    event=record_payroll_event(ctx=ctx,target_seat_id=target,payroll_event_type='payroll',
        correlation_id='raw-correlation-intent',idempotency_key='correlation-regression',mechanism='TEACHER',
        reference_time_utc=datetime(2026,8,3,18,tzinfo=timezone.utc)).payroll_event
    credit=Transaction.query.filter_by(class_id=ctx.class_id,idempotency_key='correlation-regression').one()
    assert event.correlation_id==credit.correlation_id=='corr_raw-correlation-intent'


@pytest.mark.parametrize('paid,disposition,origin',[(True,'UNPAID',None),(True,'PAID','prod-payroll:v1:999999'),
    (False,'PAID','prod-payroll:v1:999999'),(False,'UNPAID','prod-payroll:v1:999999')])
def test_prod_writer_rejects_receipt_that_disagrees_with_owned_membership(app,paid,disposition,origin):
    from datetime import datetime,timezone
    from app.feats.base import FEATContext
    from app.services.attendance_invalidation_service import record_interval_invalidation
    if paid:
        _,ctx,target,pairs,event=_paid_sources(app)
    else:
        _,ctx,target,pairs=_sources(app)
    outcomes={} if origin is None else {'original_payroll_event':origin}
    receipt={'expected_preview_identity':'opaque-preview','fingerprint_version':1,'canonical_intent_digest':'a'*64,
        'original_settlement_disposition':disposition,'opaque_outcome_locators':outcomes}
    before=(AttendanceIntervalInvalidation.query.count(),PayrollEvent.query.count(),Transaction.query.count(),AuditEvent.query.count())
    with pytest.raises(AttendanceCorrectionDenied,match='INTEGRITY_FAILURE'):
        with FEATContext('FEAT-PROD-005',idempotency_key='forged-membership-receipt'):
            record_interval_invalidation(ctx=ctx,target_seat_id=target,opening_event_id=pairs[0][0],closing_event_id=pairs[0][1],
                reason_code='INVALID_ATTENDANCE',idempotency_key='forged-membership-receipt',recorded_at=datetime.now(timezone.utc),receipt=receipt)
    assert before==(AttendanceIntervalInvalidation.query.count(),PayrollEvent.query.count(),Transaction.query.count(),AuditEvent.query.count())
