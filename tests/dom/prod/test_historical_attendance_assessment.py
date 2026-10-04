"""Phase1 diagnostic tests. Synthetic snapshots are never historical proof."""
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
import copy
import pytest

from app.extensions import db
from app.models import AttendanceSession, AuditEvent, PayrollEvent, Transaction
from app.services.context_resolver import CanonicalContext
from app.services.historical_attendance_assessment import (
    HistoricalAssessmentDenied, get_historical_attendance_business_evidence,
)
from app.services.payroll.settings import get_historical_payroll_setting_inputs
from app.services.ledger_historical_assessment import (
    HistoricalPayrollMoneyInput, HistoricalPricingInput, assess_historical_payroll_money,
    get_historical_payroll_credit_records,
)
from app.feats.historical_attendance_proof_feat import assess_historical_attendance_proof
from tests.dom.prod.test_attendance_invalidation_lineage import _sources
from tests.dom.prod.test_attendance_invalidation_command import _paid_sources


class SnapshotQuery:
    def __init__(self,rows):self.rows=rows
    def filter_by(self,**kwargs):return self
    def order_by(self,*args):return self
    def limit(self,value):return SnapshotQuery(self.rows[:value])
    def all(self):return self.rows


def _business_snapshot(app,monkeypatch,change=None,events=None):
    _,ctx,target,pairs,event=_paid_sources(app)
    attributes={name:getattr(event,name) for name in ('id','class_id','target_seat_id','actor_seat_id',
        'mechanism','payroll_event_type','correlation_id','idempotency_key','recorded_at','summary_json')}
    attributes['summary_json']=copy.deepcopy(attributes['summary_json'])
    if change:change(attributes)
    snapshot=SimpleNamespace(**attributes)
    import app.services.historical_attendance_assessment as business
    model=SimpleNamespace(query=SnapshotQuery(events or [snapshot]),recorded_at=PayrollEvent.recorded_at,id=PayrollEvent.id)
    monkeypatch.setattr(business,'PayrollEvent',model)
    settings=tuple(replace(s,created_at=datetime(2026,1,1,tzinfo=timezone.utc)) for s in get_historical_payroll_setting_inputs(ctx=ctx,class_id=ctx.class_id))
    result=get_historical_attendance_business_evidence(ctx=ctx,class_id=ctx.class_id,
        target_seat_id=target,setting_inputs=settings,as_of_utc=datetime(2026,10,3,tzinfo=timezone.utc))
    return ctx,target,pairs,event,result


def test_current_assessment_is_pure_preserves_creation_proof_and_returns_frozen_dtos(app,monkeypatch):
    _,ctx,target,pairs,event=_paid_sources(app)
    from app.utils.audit_verifier import verified_creation_evidence
    credit=Transaction.query.filter_by(idempotency_key=event.idempotency_key).one()
    proof=verified_creation_evidence('ledger_transaction',credit,ctx.class_id)
    counts=tuple(model.query.count() for model in (AttendanceSession,AuditEvent,PayrollEvent,Transaction))
    signature=(credit.lineage_event_id,credit.lineage_token,credit.lineage_version)
    # Even an unrelated pending object cannot make this assessment flush.
    pending=AttendanceSession(class_id=ctx.class_id,target_seat_id=target,actor_seat_id=ctx.seat_id,
        status='active',timestamp=datetime(2026,10,3,15,tzinfo=timezone.utc),reason_code='start_work')
    db.session.add(pending)
    monkeypatch.setattr(db.session,'flush',lambda *a,**k:pytest.fail('assessment flushed'))
    monkeypatch.setattr(db.session,'commit',lambda *a,**k:pytest.fail('assessment committed'))
    first=assess_historical_attendance_proof(ctx=ctx,target_seat_id=target)
    second=assess_historical_attendance_proof(ctx=ctx,target_seat_id=target)
    assert first==second and first.business.events[0].membership_completeness=='UNAVAILABLE'
    assert first.current_execution_eligibility=='BLOCKED_DIAGNOSTIC_ONLY'
    assert dict(first.money)[event.id].arithmetic_comparison=='MATCH'
    assert dict(first.money)[event.id].observed_credit_cents==credit.amount_cents
    assert pending in db.session.new
    with pytest.raises(FrozenInstanceError):first.business.source_visibility='PROVEN'
    with db.session.no_autoflush:
        assert counts==tuple(model.query.count() for model in (AttendanceSession,AuditEvent,PayrollEvent,Transaction))
        assert signature==(credit.lineage_event_id,credit.lineage_token,credit.lineage_version)
        assert proof==verified_creation_evidence('ledger_transaction',credit,ctx.class_id)
    db.session.expunge(pending)


@pytest.mark.parametrize('invalid',[0,True,-1,'1',None])
def test_malformed_scope_fails_before_any_evidence(app,monkeypatch,invalid):
    import app.feats.historical_attendance_proof_feat as feat
    monkeypatch.setattr(feat,'get_historical_payroll_setting_inputs',lambda **k:pytest.fail('read sources'))
    with pytest.raises(HistoricalAssessmentDenied,match='INVALID_INPUT'):
        assess_historical_attendance_proof(ctx=None,target_seat_id=invalid)


def test_cross_class_and_non_teacher_fail_before_source_queries(app,monkeypatch):
    _,ctx,target,_=_sources(app)
    import app.feats.historical_attendance_proof_feat as feat
    monkeypatch.setattr(feat,'get_historical_payroll_setting_inputs',lambda **k:pytest.fail('read sources'))
    for badctx,badtarget in ((ctx,999999),(replace(ctx,class_id='foreign'),target),
            (replace(ctx,actor_role='student'),target),(replace(ctx,user_id='00000000-0000-0000-0000-000000000000'),target)):
        with pytest.raises(HistoricalAssessmentDenied,match='UNAUTHORIZED_SCOPE'):
            assess_historical_attendance_proof(ctx=badctx,target_seat_id=badtarget)


@pytest.mark.parametrize('ids,limit',[([True],50),([1,1],50),([0],50),([1],True),([1],101),('1',50)])
def test_bad_selection_is_denied_before_read(app,ids,limit):
    with pytest.raises(HistoricalAssessmentDenied,match='INVALID_INPUT'):
        assess_historical_attendance_proof(ctx=None,target_seat_id=1,payroll_event_ids=ids,limit=limit)


def test_unknown_selected_event_denies_without_foreign_details(app):
    _,ctx,target,_=_sources(app)
    with pytest.raises(HistoricalAssessmentDenied,match='UNAUTHORIZED_SCOPE'):
        assess_historical_attendance_proof(ctx=ctx,target_seat_id=target,payroll_event_ids=[999999])


def test_attendance_budget_fails_before_pairing_not_truncated_sources(app):
    _,ctx,target,_=_sources(app)
    with pytest.raises(HistoricalAssessmentDenied,match='EVIDENCE_LIMIT_EXCEEDED'):
        get_historical_attendance_business_evidence(ctx=ctx,class_id=ctx.class_id,
            target_seat_id=target,source_limit=1,as_of_utc=datetime(2026,10,3,tzinfo=timezone.utc))


def test_missing_settings_and_historical_visibility_not_hidden_by_matching_cents(app,monkeypatch):
    ctx,target,pairs,event,result=_business_snapshot(app,monkeypatch,
        lambda e:e['summary_json'].pop('allocation_version'))
    projected=result.events[0]
    assert projected.replay_consistency=='MATCH'
    assert projected.rule.arithmetic_rule=='divide_first_half_even_28'
    assert projected.rule.record_writer_attribution=='UNAVAILABLE'
    assert projected.membership_completeness==result.source_visibility=='UNAVAILABLE'
    missing=get_historical_attendance_business_evidence(ctx=ctx,class_id=ctx.class_id,
        target_seat_id=target,setting_inputs=(),as_of_utc=datetime(2026,10,3,tzinfo=timezone.utc))
    assert missing.events[0].replay_consistency=='UNAVAILABLE'
    assert 'MISSING_OR_AMBIGUOUS_SETTING' in missing.events[0].reasons


def test_equal_seconds_wrong_frozen_membership_fails_business_replay(app,monkeypatch):
    def change(e):
        source=e['summary_json']['pricing'][0]['intervals'][0]
        source['opening_event_id']=999999
    _,_,_,_,result=_business_snapshot(app,monkeypatch,change)
    assert result.events[0].replay_consistency=='MISMATCH'
    assert 'RECORDED_MEMBERSHIP_MISMATCH' in result.events[0].reasons


@pytest.mark.parametrize('change,reason',[(lambda e:e['summary_json']['pricing'].append(copy.deepcopy(e['summary_json']['pricing'][0])),'DUPLICATE_SETTING_SHARE'),
        (lambda e:e['summary_json']['pricing'][0].update(seconds=True),'MALFORMED_PRICING')])
def test_duplicate_and_malformed_settings_never_claim_consistency(app,monkeypatch,change,reason):
    _,_,_,_,result=_business_snapshot(app,monkeypatch,change)
    assert result.events[0].replay_consistency!='MATCH'
    assert reason in result.events[0].reasons


def test_tied_payroll_boundaries_and_stale_settings_are_unavailable(app,monkeypatch):
    ctx,target,_,event,_=_business_snapshot(app,monkeypatch)
    import app.services.historical_attendance_assessment as business
    original=business.PayrollEvent.query.rows[0]
    second=copy.copy(original);second.id+=999
    business.PayrollEvent.query=SnapshotQuery([original,second])
    settings=get_historical_payroll_setting_inputs(ctx=ctx,class_id=ctx.class_id)
    stale=tuple(replace(s,created_at=datetime(2026,10,3,tzinfo=timezone.utc)) for s in settings)
    result=get_historical_attendance_business_evidence(ctx=ctx,class_id=ctx.class_id,
        target_seat_id=target,setting_inputs=stale,as_of_utc=datetime(2026,10,3,tzinfo=timezone.utc))
    assert all(e.replay_consistency=='UNAVAILABLE' for e in result.events)
    assert 'TIED_PAYROLL_BOUNDARY' in result.events[0].reasons
    assert 'SETTING_NOT_VISIBLE_AT_PAYMENT' in result.events[0].reasons


def test_repeated_active_and_dst_day_end_preserve_canonical_pairs(app):
    from tests.helpers.classroom_initializer import initialize
    from tests.dom.prod.test_payroll_closed_sessions_only import _attendance,classroom_ctx
    classroom=initialize('chemistry_p1',app);ctx=classroom_ctx(classroom);target=classroom.students[0].seat.id
    # America/Los_Angeles fall-back day includes an extra elapsed hour.
    start=datetime(2026,11,1,7,tzinfo=timezone.utc)
    end=datetime(2026,11,2,8,tzinfo=timezone.utc)
    _attendance(classroom,target,('active',start),('active',start+timedelta(hours=1)),('inactive',end))
    result=get_historical_attendance_business_evidence(ctx=ctx,class_id=ctx.class_id,target_seat_id=target,
        as_of_utc=end)
    assert len(result.intervals)==1 and result.intervals[0].credited_seconds==25*3600
    assert result.intervals[0].opening_event_id==result.source_ids[0]
    assert result.intervals[0].closing_event_id==result.source_ids[2]


def _money_input(ctx,target,rate='0.25',seconds=120):
    return HistoricalPayrollMoneyInput(ctx.class_id,target,ctx.seat_id,'teacher','payroll',
        'corr_fixture','command-fixture','divide_first_half_even_28',
        (HistoricalPricingInput('policy-fixture',seconds,rate),))


def test_zero_boundary_has_no_fake_credit_or_zero_compensation(app):
    _,ctx,target,_=_sources(app)
    result=assess_historical_payroll_money(ctx=ctx,class_id=ctx.class_id,target_seat_id=target,
        business_input=_money_input(ctx,target,rate='0'),records=())
    assert result.replay_cents==0 and result.arithmetic_comparison=='ZERO_BOUNDARY_NO_CREDIT'
    assert result.observed_credit_cents is result.credit_locator is result.recovered_cents is None


@pytest.mark.parametrize('rate',['NaN','-1','Infinity','bad'])
def test_ledger_invalid_rate_is_unavailable_not_default(app,rate):
    _,ctx,target,_=_sources(app)
    result=assess_historical_payroll_money(ctx=ctx,class_id=ctx.class_id,target_seat_id=target,
        business_input=_money_input(ctx,target,rate=rate),records=())
    assert result.replay_cents is None


def test_historical_divide_first_differs_from_current_multiply_first_at_half_cent(app):
    _,ctx,target,_=_sources(app)
    inputs=_money_input(ctx,target,rate='0.01',seconds=30)
    result=assess_historical_payroll_money(ctx=ctx,class_id=ctx.class_id,target_seat_id=target,
        business_input=inputs,records=())
    current=assess_historical_payroll_money(ctx=ctx,class_id=ctx.class_id,target_seat_id=target,
        business_input=replace(inputs,arithmetic_rule='multiply_first_half_even_28'),records=())
    assert result.replay_cents==1 and current.replay_cents==0


def test_unknown_compensation_remains_none_and_ambiguous_credit_identity_denies(app):
    _,ctx,target,_,event=_paid_sources(app)
    records=get_historical_payroll_credit_records(ctx=ctx,class_id=ctx.class_id,target_seat_id=target)
    inputs=replace(_money_input(ctx,target),correlation_id=event.correlation_id,command_key=event.idempotency_key)
    result=assess_historical_payroll_money(ctx=ctx,class_id=ctx.class_id,target_seat_id=target,
        business_input=inputs,records=records)
    assert result.credit_identity=='UNIQUE_SCOPED_CANDIDATE'
    assert result.recovered_cents is None
    result=assess_historical_payroll_money(ctx=ctx,class_id=ctx.class_id,target_seat_id=target,
        business_input=inputs,records=records+records)
    assert result.credit_identity=='UNAVAILABLE' and result.observed_credit_cents is None


def test_future_setting_without_original_pricing_never_substitutes_new_rate(app,monkeypatch):
    ctx,target,_,_,_= _business_snapshot(app,monkeypatch,
        lambda e:(e['summary_json'].pop('allocation_version'),e['summary_json'].pop('pricing')))
    settings=get_historical_payroll_setting_inputs(ctx=ctx,class_id=ctx.class_id)
    future=tuple(replace(s,created_at=datetime(2026,10,3,tzinfo=timezone.utc),rate_per_minute='99') for s in settings)
    result=get_historical_attendance_business_evidence(ctx=ctx,class_id=ctx.class_id,
        target_seat_id=target,setting_inputs=future,as_of_utc=datetime(2026,10,3,tzinfo=timezone.utc))
    assert not result.events[0].pricing_inputs
    assert 'SETTING_NOT_VISIBLE_AT_PAYMENT' in result.events[0].reasons


def test_swapping_equal_duration_pairs_across_setting_shares_is_mismatch(app,monkeypatch):
    ctx,target,pairs,event,_=_business_snapshot(app,monkeypatch)
    import app.services.historical_attendance_assessment as business
    snapshot=business.PayrollEvent.query.rows[0]
    first=snapshot.summary_json['pricing'][0]
    sources=first['intervals']
    settings=get_historical_payroll_setting_inputs(ctx=ctx,class_id=ctx.class_id)
    original=replace(settings[0],created_at=datetime(2026,1,1,tzinfo=timezone.utc),
        effective_at=datetime(2026,1,1,tzinfo=timezone.utc))
    later=replace(original,policy_locator='second-policy',effective_at=datetime(2026,8,2,tzinfo=timezone.utc))
    snapshot.summary_json['pricing']=[dict(policy_uuid=original.policy_locator,seconds=120,
        pay_rate_per_minute=original.rate_per_minute,intervals=[sources[1]]),
        dict(policy_uuid=later.policy_locator,seconds=120,pay_rate_per_minute=later.rate_per_minute,intervals=[sources[0]])]
    result=get_historical_attendance_business_evidence(ctx=ctx,class_id=ctx.class_id,
        target_seat_id=target,setting_inputs=(original,later),as_of_utc=datetime(2026,10,3,tzinfo=timezone.utc))
    assert result.events[0].replay_consistency=='MISMATCH'
    assert 'RECORDED_SHARE_MEMBERSHIP_MISMATCH' in result.events[0].reasons


def test_event_and_setting_budgets_never_return_truncated_replay(app,monkeypatch):
    ctx,target,_,_,_=_business_snapshot(app,monkeypatch)
    import app.services.historical_attendance_assessment as business
    row=business.PayrollEvent.query.rows[0]
    business.PayrollEvent.query=SnapshotQuery([row,row])
    monkeypatch.setattr(business,'list_attendance_interval_evidence',lambda *a,**k:pytest.fail('paired truncated source'))
    with pytest.raises(HistoricalAssessmentDenied,match='EVIDENCE_LIMIT_EXCEEDED'):
        get_historical_attendance_business_evidence(ctx=ctx,class_id=ctx.class_id,target_seat_id=target,event_limit=1)
    import app.services.payroll.settings as policies
    inputrow=SimpleNamespace(class_id=ctx.class_id,policy_uuid='policy',effective_date=datetime(2026,1,1,tzinfo=timezone.utc),
        created_at=datetime(2026,1,1,tzinfo=timezone.utc),pay_rate=Decimal('.25'))
    monkeypatch.setattr(policies,'_for_class',lambda *a:SnapshotQuery([inputrow,inputrow]))
    with pytest.raises(ValueError,match='EVIDENCE_LIMIT_EXCEEDED'):
        get_historical_payroll_setting_inputs(ctx=ctx,class_id=ctx.class_id,limit=1)


def test_monetary_history_budget_and_foreign_direct_scope_deny_before_analysis(app,monkeypatch):
    _,ctx,target,_,event=_paid_sources(app)
    import app.services.ledger_historical_assessment as ledger
    rows=get_historical_payroll_credit_records(ctx=ctx,class_id=ctx.class_id,target_seat_id=target)
    monkeypatch.setattr(ledger,'Transaction',SimpleNamespace(query=SnapshotQuery(rows+rows),id=Transaction.id))
    with pytest.raises(ValueError,match='EVIDENCE_LIMIT_EXCEEDED'):
        get_historical_payroll_credit_records(ctx=ctx,class_id=ctx.class_id,target_seat_id=target,limit=1)
    with pytest.raises(ValueError,match='UNAUTHORIZED_SCOPE'):
        get_historical_payroll_credit_records(ctx=ctx,class_id='foreign',target_seat_id=target)


def test_legacy_open_fragment_remains_unsupported_attribution(app,monkeypatch):
    _,_,_,_,result=_business_snapshot(app,monkeypatch,
        lambda e:e.update(summary_json={}))
    projected=result.events[0]
    assert projected.rule.version.startswith('open_fragment:')
    assert not projected.candidate_sources and not projected.pricing_inputs
    assert projected.membership_completeness=='UNAVAILABLE'
    assert 'FRAGMENT_OR_MANUAL_ATTRIBUTION_NOT_ADMITTED' in projected.reasons


def test_boolean_source_ids_cannot_masquerade_as_canonical_integer_membership(app,monkeypatch):
    def change(e):
        source=e['summary_json']['pricing'][0]['intervals'][0]
        source['opening_event_id']=True
    _,_,_,_,result=_business_snapshot(app,monkeypatch,change)
    assert result.events[0].replay_consistency=='UNAVAILABLE'
    assert 'MALFORMED_PRICING' in result.events[0].reasons
