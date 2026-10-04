"""Selection regression tests; Ledger independently proves the resulting cents."""
from dataclasses import FrozenInstanceError
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace as NS
import pytest
import uuid
from app.services.attendance_service import AttendanceInterval
from app.services.historical_payroll_reconstruction import reconstruct_historical_payroll_snapshot as reconstruct
from app.services.historical_attendance_assessment import HistoricalAssessmentDenied

BASE=datetime(2026,9,28,15,tzinfo=timezone.utc)
CTX=NS(class_id='class-fixture',seat_id=10,user_id='teacher',actor_role='teacher')

def row(pk,status,seconds):
    return NS(id=pk,status=status,timestamp=BASE+timedelta(seconds=seconds),class_id=CTX.class_id,target_seat_id=20)

def pair(a,b,start,end):
    return AttendanceInterval(a,b,BASE+timedelta(seconds=start),BASE+timedelta(seconds=end),int(end-start),'self','self')

def event(pk,seconds,summary=None,kind='payroll'):
    topup=kind=='manual_credit' and summary and summary.get('incident')=='PROD-PAY-001'
    key=f'payroll-correction:PROD-PAY-001:{CTX.class_id}:20' if topup else f'key-{pk}'
    if topup: summary={**summary,'approved_by_seat_id':10}
    return NS(id=pk,recorded_at=BASE+timedelta(seconds=seconds),summary_json=summary or {},payroll_event_type=kind,
        class_id=CTX.class_id,target_seat_id=20,actor_seat_id=10,mechanism='SYSTEM' if topup else 'TEACHER',
        correlation_id=str(uuid.uuid5(uuid.NAMESPACE_URL,key)) if topup else f'corr-{pk}',idempotency_key=key)

def replay(monkeypatch,rows,pairs,events,settings=None):
    import app.services.historical_payroll_reconstruction as prod
    monkeypatch.setattr(prod,'_day_end_utc',lambda ctx,t:BASE+timedelta(hours=9))
    settings=settings or (NS(class_id=CTX.class_id,policy_locator='setting',rate_per_minute='0.25',legacy_rate_per_minute='0.25',
        effective_at=BASE-timedelta(days=1),created_at=BASE-timedelta(days=1)),)
    return reconstruct(ctx=CTX,target_seat_id=20,rows=tuple(rows),intervals=tuple(pairs),events=tuple(events),setting_inputs=settings)

def test_closed_share_truncates_aggregate_once_and_is_frozen(monkeypatch):
    rows=[row(1,'active',0),row(2,'inactive',.6),row(3,'active',1),row(4,'inactive',1.6)]
    result=replay(monkeypatch,rows,[pair(1,2,0,.6),pair(3,4,1,1.6)],[event(1,2,{'settlement_rule':'closed_sessions'})])
    share=result.events[0].shares[0]
    assert share.credited_seconds==1
    assert [w.duration_microseconds for w in share.weights]==[600000,600000]
    with pytest.raises(FrozenInstanceError):share.credited_seconds=5

def test_legacy_restart_fragment_closed_remainder_and_zero_boundary(monkeypatch):
    rows=[row(1,'active',0),row(2,'active',10),row(3,'inactive',100)]
    result=replay(monkeypatch,rows,[pair(1,3,0,100)],
        [event(1,30),event(2,50),event(3,110,{'settlement_rule':'closed_sessions'})])
    assert [sum(s.credited_seconds for s in e.shares) for e in result.events]==[20,0,50]
    assert result.events[0].shares[0].weights[0].opening_event_id==1
    assert result.events[0].shares[0].source_segments==((row(2,'active',10).timestamp.isoformat(),event(1,30).recorded_at.isoformat()),)

def test_incident_topup_reconstructs_positive_loss_per_original_window(monkeypatch):
    rows=[row(1,'active',0),row(2,'inactive',100)]
    events=[event(1,30),event(2,60),event(3,110,{'settlement_rule':'closed_sessions'}),
        event(4,120,{'source':'payroll_correction','incident':'PROD-PAY-001','corrected_payroll_event_ids':[2]},'manual_credit')]
    result=replay(monkeypatch,rows,[pair(1,2,0,100)],events)
    share=result.events[-1].shares[0]
    assert share.window_event_id==2 and share.credited_seconds==30 and share.paid_seconds==0
    assert share.weights[0].duration_microseconds==30000000
    assert [e.event_id for e in result.events]==[1,2,3,4]

def test_reversal_relationship_retained_without_money(monkeypatch):
    result=replay(monkeypatch,[row(1,'active',0),row(2,'inactive',60)],[pair(1,2,0,60)],
        [event(1,70,{'settlement_rule':'closed_sessions'}),event(2,80,{'reversed_payroll_event_id':1},'reversal')])
    assert result.reversals[0].original_event_id==1
    assert result.reversals[0].event.event_id==2

@pytest.mark.parametrize('events,reason',[
    ([event(1,70),event(2,70)],'TIED_PAYROLL_BOUNDARY'),
    ([event(1,70,{'allocation_version':2})],'UNKNOWN_ALLOCATION_VERSION'),
    ([event(1,70),event(2,80,{'source':'payroll_correction','incident':'PROD-PAY-001','corrected_payroll_event_ids':[999]},'manual_credit')],'TOPUP_MEMBERSHIP_UNAVAILABLE'),
])
def test_ambiguous_or_unrecognized_graph_denies(monkeypatch,events,reason):
    with pytest.raises(HistoricalAssessmentDenied,match=reason):
        replay(monkeypatch,[row(1,'active',0),row(2,'inactive',60)],[pair(1,2,0,60)],events)

def test_unclosed_pair_and_cross_class_deny(monkeypatch):
    with pytest.raises(HistoricalAssessmentDenied,match='INCOMPLETE_CANONICAL_PAIR'):
        replay(monkeypatch,[row(1,'active',0)],[pair(1,None,0,100)],[event(1,30)])
    foreign=row(1,'active',0);foreign.class_id='foreign'
    with pytest.raises(HistoricalAssessmentDenied,match='UNAUTHORIZED_SCOPE'):
        replay(monkeypatch,[foreign],[pair(1,2,0,100)],[event(1,30)])

def test_historical_settings_group_by_close_not_latest_payment_rate(monkeypatch):
    settings=(NS(class_id=CTX.class_id,policy_locator='old',rate_per_minute='0.25',legacy_rate_per_minute='0.25',effective_at=BASE-timedelta(days=1),created_at=BASE-timedelta(days=1)),
        NS(class_id=CTX.class_id,policy_locator='new',rate_per_minute='0.50',legacy_rate_per_minute='0.50',effective_at=BASE+timedelta(seconds=50),created_at=BASE-timedelta(hours=1)))
    result=replay(monkeypatch,[row(1,'active',0),row(2,'inactive',30),row(3,'active',60),row(4,'inactive',90)],
        [pair(1,2,0,30),pair(3,4,60,90)],[event(1,100,{'settlement_rule':'closed_sessions'})],settings)
    assert [(s.policy_locator,s.rate_per_minute,s.credited_seconds) for s in result.events[0].shares]==[('old','0.25',30),('new','0.50',30)]

def test_modern_malformed_frozen_membership_never_uses_historical_fallback(monkeypatch):
    with pytest.raises(HistoricalAssessmentDenied,match='RECORDED_MEMBERSHIP_MISMATCH'):
        replay(monkeypatch,[row(1,'active',0),row(2,'inactive',60)],[pair(1,2,0,60)],
            [event(1,70,{'allocation_version':1,'settlement_rule':'closed_sessions'})])

def test_modern_partial_recovery_business_projection_is_scoped(monkeypatch):
    result=replay(monkeypatch,[row(1,'active',0),row(2,'inactive',60)],[pair(1,2,0,60)],
        [event(1,70,{'settlement_rule':'closed_sessions'}),event(2,80,{'original_payroll_event_id':1,
            'correction_intent':'INTERVAL_INVALIDATION','opening_event_id':1,'closing_event_id':2,
            'correction_intent_locator':'intent','ledger_result_locator':'result'},'correction')])
    assert result.recoveries[0].opening_event_id==1
    assert result.recoveries[0].original_event_id==1

def test_topup_exposes_all_loss_windows_for_ledger_positive_selection_check(monkeypatch):
    rows=[row(1,'active',0),row(2,'inactive',100)]
    result=replay(monkeypatch,rows,[pair(1,2,0,100)],
        [event(1,20),event(2,40),event(3,60),event(4,120,{'source':'payroll_correction','incident':'PROD-PAY-001','corrected_payroll_event_ids':[2]},'manual_credit')])
    topup=result.events[-1]
    assert [s.window_event_id for s in topup.shares]==[2]
    assert [s.window_event_id for s in topup.candidate_shares]==[2,3]

def test_original_first_setting_fallback_has_no_created_at_visibility_filter(monkeypatch):
    settings=(NS(class_id=CTX.class_id,policy_locator='first',rate_per_minute='0.25',legacy_rate_per_minute='0.25',
        effective_at=BASE+timedelta(days=3),created_at=BASE+timedelta(days=2)),)
    result=replay(monkeypatch,[row(1,'active',0),row(2,'inactive',60)],[pair(1,2,0,60)],
        [event(1,70,{'settlement_rule':'closed_sessions'})],settings)
    assert result.events[0].shares[0].policy_locator=='first'

def test_zero_duration_completed_pair_retains_identity_for_zero_cent_outcome(monkeypatch):
    result=replay(monkeypatch,[row(1,'active',0),row(2,'inactive',0)],[pair(1,2,0,0)],
        [event(1,10,{'settlement_rule':'closed_sessions'})])
    share=result.events[0].shares[0]
    assert share.credited_seconds==0 and share.weights[0].duration_microseconds==0
    assert share.weights[0].opening_event_id==1 and share.weights[0].closing_event_id==2

def test_retained_original_pricing_contradiction_denies_even_equal_total_seconds(monkeypatch):
    with pytest.raises(HistoricalAssessmentDenied,match='RECORDED_PRICING_MISMATCH'):
        replay(monkeypatch,[row(1,'active',0),row(2,'inactive',60)],[pair(1,2,0,60)],
            [event(1,70,{'settlement_rule':'closed_sessions','pricing':[
                {'policy_uuid':'different','seconds':60,'pay_rate_per_minute':'0.25'}]})])

def test_boolean_frozen_source_ids_cannot_match_integer_canonical_pair(monkeypatch):
    interval=pair(1,2,0,60)
    evidence=interval.as_evidence();evidence['opening_event_id']=True
    with pytest.raises(HistoricalAssessmentDenied,match='RECORDED_MEMBERSHIP_MISMATCH'):
        replay(monkeypatch,[row(1,'active',0),row(2,'inactive',60)],[interval],
            [event(1,70,{'allocation_version':1,'settlement_rule':'closed_sessions','pricing':[
                {'policy_uuid':'setting','seconds':60,'pay_rate_per_minute':'0.25','intervals':[evidence]}]})])

def test_closed_writer_keeps_raw_zero_rate_legacy_open_writer_uses_policy_effective_rate(monkeypatch):
    setting=NS(class_id=CTX.class_id,policy_locator='zero',rate_per_minute='0.00',legacy_rate_per_minute='0.25',
        effective_at=BASE-timedelta(days=1),created_at=BASE-timedelta(days=1))
    rows=[row(1,'active',0),row(2,'inactive',60)];pairs=[pair(1,2,0,60)]
    closed=replay(monkeypatch,rows,pairs,[event(1,70,{'settlement_rule':'closed_sessions'})],(setting,))
    legacy=replay(monkeypatch,rows,pairs,[event(1,70)],(setting,))
    assert closed.events[0].shares[0].rate_per_minute=='0.00'
    assert legacy.events[0].shares[0].rate_per_minute=='0.25'

@pytest.mark.parametrize('closed_rule',[False,True])
def test_mixed_legacy_modern_membership_retains_reconstruction_requirement(monkeypatch,closed_rule):
    import app.services.payroll_interval_provenance as prod
    from app.models import PayrollEvent
    interval=pair(1,2,0,60)
    old=event(1,70 if closed_rule else 30,{'settlement_rule':'closed_sessions'} if closed_rule else {})
    modern=event(2,80,{'allocation_version':1,'settlement_rule':'closed_sessions','pricing':[
        {'policy_uuid':'setting','seconds':60,'pay_rate_per_minute':'0.25','intervals':[interval.as_evidence()]}]})
    class Query:
        def filter_by(self,**kwargs):return self
        def order_by(self,*args):return self
        def all(self):return [old,modern]
    monkeypatch.setattr(prod,'PayrollEvent',NS(query=Query(),recorded_at=PayrollEvent.recorded_at,id=PayrollEvent.id))
    monkeypatch.setattr(prod,'list_attendance_intervals',lambda *a,**k:(interval,))
    membership=prod.payroll_interval_memberships(20,CTX.class_id,ctx=CTX)[1,2]
    assert membership['status']=='recorded' and membership['event'] is modern
    assert membership['requires_reconstruction'] is True


def test_closed_zero_boundary_does_not_mark_still_open_work_historically_paid(monkeypatch):
    import app.services.payroll_interval_provenance as prod
    from app.models import PayrollEvent
    interval=pair(1,2,0,60)
    old=event(1,30,{'settlement_rule':'closed_sessions'})
    class Query:
        def filter_by(self,**kwargs):return self
        def order_by(self,*args):return self
        def all(self):return [old]
    monkeypatch.setattr(prod,'PayrollEvent',NS(query=Query(),recorded_at=PayrollEvent.recorded_at,id=PayrollEvent.id))
    monkeypatch.setattr(prod,'list_attendance_intervals',lambda *a,**k:(interval,))
    membership=prod.payroll_interval_memberships(20,CTX.class_id,ctx=CTX)[1,2]
    assert membership['status']=='unpaid' and membership['requires_reconstruction'] is False
