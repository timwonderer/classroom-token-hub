"""PROD-owned immutable historical selection (DOM-PROD-001 §XV.9–10).

This query supplies business facts, not monetary or audit conclusions. The FEAT
supplies retained Policies inputs and Ledger independently checks original price.
"""
from dataclasses import dataclass
import uuid
from app.extensions import db
from app.models import PayrollEvent
from app.services.attendance_service import list_attendance_interval_evidence, _day_end_utc
from app.services.historical_attendance_assessment import HistoricalAssessmentDenied, _scope, _setting_for
from app.utils.canonical_temporal_resolver import ensure_utc


@dataclass(frozen=True)
class HistoricalPairWeight:
    opening_event_id: int
    closing_event_id: int
    closing_timestamp: str
    duration_microseconds: int


@dataclass(frozen=True)
class HistoricalReconstructedShare:
    policy_locator: str
    rate_per_minute: str
    credited_seconds: int
    weights: tuple
    window_event_id: int
    paid_seconds: int | None = None
    source_segments: tuple = ()


@dataclass(frozen=True)
class HistoricalReconstructedEvent:
    event_id: int
    class_id: str
    target_seat_id: int
    actor_seat_id: int
    mechanism: str
    event_type: str
    correlation_id: str
    command_key: str
    recorded_at: object
    arithmetic_rule: str
    shares: tuple
    referenced_event_ids: tuple = ()
    candidate_shares: tuple = ()


@dataclass(frozen=True)
class HistoricalReconstructedReversal:
    original_event_id: int
    event: HistoricalReconstructedEvent


@dataclass(frozen=True)
class HistoricalReconstructedRecovery:
    event_id: int
    original_event_id: int
    correction_intent_locator: str
    opening_event_id: int | None
    closing_event_id: int | None
    kind: str
    ledger_result_locator: str
    class_id: str
    target_seat_id: int


@dataclass(frozen=True)
class HistoricalReconstructedGraph:
    class_id: str
    target_seat_id: int
    source_ids: tuple
    intervals: tuple
    events: tuple
    reversals: tuple
    recoveries: tuple = ()
    source_records: tuple = ()
    setting_inputs: tuple = ()


def _deny(reason):
    raise HistoricalAssessmentDenied(reason)


def _microseconds(start, end):
    delta = end - start
    return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds


def _weights(segments, intervals):
    grouped = {}
    seen = {}
    for start, end in segments:
        if end < start:
            _deny('CONFLICTING_SELECTION')
        matches = [i for i in intervals if i.opened_at <= start and end <= i.closed_at]
        if end == start:
            exact = [i for i in matches if i.opened_at == start and i.closed_at == end]
            if exact: matches = exact
        if len(matches) != 1 or matches[0].closing_event_id is None:
            _deny('INCOMPLETE_CANONICAL_PAIR')
        pair = matches[0]
        key = (pair.opening_event_id, pair.closing_event_id)
        if any(start < b and a < end for a, b in seen.get(key, ())):
            _deny('CONFLICTING_SELECTION')
        seen.setdefault(key, []).append((start, end))
        grouped[key] = grouped.get(key, 0) + _microseconds(start, end)
    pairs = {(i.opening_event_id, i.closing_event_id): i for i in intervals}
    return tuple(HistoricalPairWeight(a,b,ensure_utc(pairs[a,b].closed_at).isoformat(),duration)
        for (a,b),duration in sorted(grouped.items()))


def _legacy_segments(rows, *, ctx, previous, at):
    """c42f882b _calculate_attendance_seconds_since: restart; >= lower bound."""
    result, opened = [], None
    for row in rows:
        timestamp = ensure_utc(row.timestamp)
        if timestamp > at:
            break
        if previous is not None and timestamp < previous:
            continue
        if row.status == 'active':
            opened = timestamp
        elif row.status == 'inactive' and opened is not None:
            result.append((opened, min(timestamp, _day_end_utc(ctx, opened))))
            opened = None
    if opened is not None:
        result.append((opened, min(at, _day_end_utc(ctx, opened))))
    return tuple(result)


def _worked_segments(intervals, previous, at):
    return tuple((max(i.opened_at, previous) if previous else i.opened_at,min(i.closed_at,at))
        for i in intervals if i.opened_at < at and (previous is None or i.closed_at > previous))


def _difference(worked, paid):
    """Exact nonoverlapping temporal set difference, never scalar subtraction."""
    result = list(worked)
    for start,end in paid:
        containing = [(a,b) for a,b in worked if a <= start and end <= b]
        if end < start or len(containing) != 1:
            _deny('PAID_OUTSIDE_WORKED')
        next_result = []
        for a,b in result:
            if end <= a or start >= b:
                next_result.append((a,b))
            else:
                if a < start: next_result.append((a,start))
                if end < b: next_result.append((end,b))
        result = next_result
    return tuple(result)


def _share(settings, instant, segments, intervals, window, *, paid=None, legacy=True):
    setting = _setting_for(settings, instant)
    if setting is None:
        _deny('MISSING_OR_AMBIGUOUS_SETTING')
    weights = _weights(segments,intervals)
    rate = setting.legacy_rate_per_minute if legacy else setting.rate_per_minute
    if not isinstance(rate,str): _deny('MISSING_OR_AMBIGUOUS_SETTING')
    return HistoricalReconstructedShare(setting.policy_locator,rate,
        sum(_microseconds(a,b) for a,b in segments)//1000000,weights,window,paid,tuple((a.isoformat(),b.isoformat()) for a,b in segments))


def _event(event, shares, rule, references=(), candidates=()):
    return HistoricalReconstructedEvent(event.id,event.class_id,event.target_seat_id,
        event.actor_seat_id,event.mechanism,event.payroll_event_type,event.correlation_id,
        event.idempotency_key,ensure_utc(event.recorded_at),rule,tuple(shares),tuple(references),tuple(candidates))


def reconstruct_historical_payroll_graph(*,ctx,target_seat_id,setting_inputs,
        source_limit=2000,event_limit=1000,as_of_utc=None):
    """Read the complete scoped graph before any presentation pagination."""
    _scope(ctx,ctx.class_id,target_seat_id)
    if (type(event_limit) is not int or not 1 <= event_limit <= 1000
            or len(setting_inputs)>500):
        _deny('INVALID_INPUT')
    if any(s.class_id != ctx.class_id for s in setting_inputs):
        _deny('UNAUTHORIZED_SCOPE')
    with db.session.no_autoflush:
        rows,intervals = list_attendance_interval_evidence(target_seat_id,ctx.class_id,
            ctx=ctx,as_of_utc=as_of_utc,source_limit=source_limit)
        events = PayrollEvent.query.filter_by(class_id=ctx.class_id,target_seat_id=target_seat_id).order_by(
            PayrollEvent.recorded_at.asc(),PayrollEvent.id.asc()).limit(event_limit+1).all()
        if len(events)>event_limit: _deny('EVIDENCE_LIMIT_EXCEEDED')
        return reconstruct_historical_payroll_snapshot(ctx=ctx,target_seat_id=target_seat_id,
            rows=rows,intervals=intervals,events=events,setting_inputs=setting_inputs)


def reconstruct_historical_payroll_snapshot(*,ctx,target_seat_id,rows,intervals,events,setting_inputs):
    """Internal pure evaluator of the bounded owning-domain snapshot."""
    _scope(ctx,ctx.class_id,target_seat_id)
    if any(r.class_id != ctx.class_id or r.target_seat_id != target_seat_id for r in (*rows,*events)):
        _deny('UNAUTHORIZED_SCOPE')
    settings = tuple(sorted(setting_inputs,key=lambda s:(ensure_utc(s.effective_at),ensure_utc(s.created_at))))
    if any(s.class_id != ctx.class_id for s in settings): _deny('UNAUTHORIZED_SCOPE')
    ordered = sorted(events,key=lambda e:(ensure_utc(e.recorded_at),e.id))
    payroll = [e for e in ordered if e.payroll_event_type == 'payroll']
    if len({ensure_utc(e.recorded_at) for e in payroll}) != len(payroll):
        _deny('TIED_PAYROLL_BOUNDARY')
    result, window_facts, previous, legacy_times = [], {}, None, []
    for event in payroll:
        at = ensure_utc(event.recorded_at)
        if event.summary_json is not None and not isinstance(event.summary_json,dict):
            _deny('MALFORMED_PAYROLL_EVIDENCE')
        summary = event.summary_json or {}
        if summary.get('settlement_rule') not in (None,'closed_sessions'):
            _deny('UNKNOWN_SETTLEMENT_RULE')
        if 'allocation_version' in summary and (type(summary['allocation_version']) is not int or summary['allocation_version'] != 1):
            _deny('UNKNOWN_ALLOCATION_VERSION')
        if summary.get('allocation_version') == 1:
            if not isinstance(summary.get('pricing'),list):
                _deny('RECORDED_MEMBERSHIP_MISMATCH')
            shares = []
            seen, policies = set(), set()
            for frozen in summary.get('pricing', ()):
                if (not isinstance(frozen,dict) or not isinstance(frozen.get('intervals'),list)
                        or type(frozen.get('seconds')) is not int or frozen['seconds'] < 0
                        or not isinstance(frozen.get('policy_uuid'),str)
                        or frozen['policy_uuid'] in policies):
                    _deny('RECORDED_MEMBERSHIP_MISMATCH')
                policies.add(frozen['policy_uuid'])
                segments = []
                for source in frozen.get('intervals', ()):
                    if (not isinstance(source,dict) or any(type(source.get(field)) is not int or source[field] <= 0
                            for field in ('opening_event_id','closing_event_id'))
                            or type(source.get('credited_seconds')) is not int or source['credited_seconds'] < 0):
                        _deny('RECORDED_MEMBERSHIP_MISMATCH')
                    key = (source.get('opening_event_id'),source.get('closing_event_id'))
                    matches = [i for i in intervals if (i.opening_event_id,i.closing_event_id) == key]
                    if (key in seen or len(matches) != 1 or matches[0].closed_at > at
                            or matches[0].as_evidence() != source):
                        _deny('RECORDED_MEMBERSHIP_MISMATCH')
                    seen.add(key)
                    segments.append((matches[0].opened_at,matches[0].closed_at))
                if not segments: _deny('RECORDED_MEMBERSHIP_MISMATCH')
                share = _share(settings,segments[0][1],tuple(segments),intervals,event.id,legacy=False)
                if (share.policy_locator != frozen.get('policy_uuid') or share.rate_per_minute != frozen.get('pay_rate_per_minute')
                        or share.credited_seconds != frozen.get('seconds')):
                    _deny('RECORDED_MEMBERSHIP_MISMATCH')
                shares.append(share)
            if not shares: _deny('RECORDED_MEMBERSHIP_MISMATCH')
        elif summary.get('settlement_rule') != 'closed_sessions':
            segments = _legacy_segments(rows,ctx=ctx,previous=previous,at=at)
            shares = [_share(settings,at,segments,intervals,event.id)]
            worked = _worked_segments(intervals,previous,at)
            window_facts[event.id] = (event,segments,worked)
            legacy_times.append(at)
        else:
            groups = {}
            for interval in intervals:
                end = interval.closed_at
                if end > at or (previous and end <= previous): continue
                start = interval.opened_at
                earlier = [t for t in legacy_times if t < end]
                if earlier: start = max(start,max(earlier))
                if end < start: continue
                setting = _setting_for(settings,end)
                if setting is None: _deny('MISSING_OR_AMBIGUOUS_SETTING')
                groups.setdefault(setting.policy_locator,[]).append((start,end))
            shares = [_share(settings,segments[0][1],tuple(segments),intervals,event.id,legacy=False)
                for segments in groups.values()]
        if summary.get('allocation_version') != 1 and 'pricing' in summary:
            recorded = summary['pricing']
            if (not isinstance(recorded,list) or any(not isinstance(v,dict)
                    or type(v.get('seconds')) is not int or v['seconds'] < 0
                    or not isinstance(v.get('policy_uuid'),str)
                    or not isinstance(v.get('pay_rate_per_minute'),str) for v in recorded)
                    or sorted((v['policy_uuid'],v['seconds'],v['pay_rate_per_minute']) for v in recorded)
                    != sorted((v.policy_locator,v.credited_seconds,v.rate_per_minute) for v in shares if v.credited_seconds > 0)):
                _deny('RECORDED_PRICING_MISMATCH')
        rule = ('multiply_first_half_even_28' if summary.get('allocation_version') == 1
            else 'divide_first_half_even_28')
        result.append(_event(event,shares,rule))
        previous = at  # Zero runs and every nonlegacy run remain boundaries.
    known = {e.id:e for e in ordered}
    reversals, recoveries = [], []
    for event in ordered:
        if event.summary_json is not None and not isinstance(event.summary_json,dict):
            _deny('MALFORMED_PAYROLL_EVIDENCE')
        summary = event.summary_json or {}
        if (event.payroll_event_type == 'manual_credit' and summary.get('source') == 'payroll_correction'
                and summary.get('incident') == 'PROD-PAY-001'):
            expected_key = f'payroll-correction:PROD-PAY-001:{ctx.class_id}:{target_seat_id}'
            expected_correlation = str(uuid.uuid5(uuid.NAMESPACE_URL,expected_key))
            if (event.idempotency_key != expected_key or event.correlation_id != expected_correlation
                    or str(event.mechanism).lower() != 'system'
                    or type(summary.get('approved_by_seat_id')) is not int
                    or summary['approved_by_seat_id'] != event.actor_seat_id):
                _deny('TOPUP_MEMBERSHIP_UNAVAILABLE')
            references = summary.get('corrected_payroll_event_ids')
            if (not isinstance(references,list) or not references
                    or any(type(i) is not int for i in references) or len(set(references)) != len(references)
                    or any(i not in window_facts
                        or ensure_utc(window_facts[i][0].recorded_at) >= ensure_utc(event.recorded_at)
                        for i in references)):
                _deny('TOPUP_MEMBERSHIP_UNAVAILABLE')
            candidates = []
            for ref,(original,paid,worked) in window_facts.items():
                if ensure_utc(original.recorded_at) >= ensure_utc(event.recorded_at):
                    continue
                paid_seconds = sum(_microseconds(a,b) for a,b in paid)//1000000
                worked_seconds = sum(_microseconds(a,b) for a,b in worked)//1000000
                if worked_seconds <= paid_seconds:
                    continue
                _weights(paid,intervals)
                loss = _difference(worked,paid)
                base = _share(settings,ensure_utc(original.recorded_at),worked,intervals,ref,paid=paid_seconds)
                candidates.append(HistoricalReconstructedShare(base.policy_locator,base.rate_per_minute,
                    base.credited_seconds,_weights(loss,intervals),ref,paid_seconds,
                    tuple((a.isoformat(),b.isoformat()) for a,b in loss)))
            candidates_by_id = {share.window_event_id:share for share in candidates}
            if any(ref not in candidates_by_id for ref in references):
                _deny('TOPUP_MEMBERSHIP_UNAVAILABLE')
            shares = [candidates_by_id[ref] for ref in references]
            result.append(_event(event,shares,'divide_first_half_even_28',references,candidates))
        elif event.payroll_event_type == 'correction' or (event.payroll_event_type == 'reversal' and 'command_receipt' in summary):
            ref = summary.get('original_payroll_event_id')
            if type(ref) is not int or ref not in known:
                _deny('COMPENSATION_MEMBERSHIP_UNAVAILABLE')
            recoveries.append(HistoricalReconstructedRecovery(event.id,ref,summary.get('correction_intent_locator'),
                summary.get('opening_event_id'),summary.get('closing_event_id'),
                summary.get('correction_intent','EXACT_REVERSAL'),summary.get('ledger_result_locator'),
                event.class_id,event.target_seat_id))
        elif event.payroll_event_type == 'reversal':
            ref = summary.get('reversed_payroll_event_id')
            if type(ref) is not int or ref not in known or known[ref].payroll_event_type not in {'payroll','manual_credit'}:
                _deny('COMPENSATION_MEMBERSHIP_UNAVAILABLE')
            reversals.append(HistoricalReconstructedReversal(ref,_event(event,(),'reversal')))
    return HistoricalReconstructedGraph(ctx.class_id,target_seat_id,tuple(r.id for r in rows),
        tuple(intervals),tuple(sorted(result,key=lambda e:(e.recorded_at,e.event_id))),tuple(reversals),tuple(recoveries),
        tuple((r.id,ensure_utc(r.timestamp).isoformat(),r.status) for r in rows),settings)


def get_historical_reconstruction_business_records(*,ctx,target_seat_id):
    """PROD-owned bounded rows for FEAT-supplied Operations evidence checks."""
    _scope(ctx,ctx.class_id,target_seat_id)
    with db.session.no_autoflush:
        rows = PayrollEvent.query.filter_by(class_id=ctx.class_id,target_seat_id=target_seat_id).order_by(
            PayrollEvent.recorded_at.asc(),PayrollEvent.id.asc()).limit(1001).all()
    if len(rows)>1000: _deny('EVIDENCE_LIMIT_EXCEEDED')
    return tuple(rows)


def reconstructed_pair_events(graph,*,ctx,target_seat_id,opening_event_id,closing_event_id):
    """Validate the owning-domain immutable graph's pair membership for writes."""
    if (not isinstance(graph,HistoricalReconstructedGraph) or graph.class_id != ctx.class_id
            or graph.target_seat_id != target_seat_id):
        _deny('UNAUTHORIZED_SCOPE')
    if not any(i.opening_event_id==opening_event_id and i.closing_event_id==closing_event_id
            for i in graph.intervals):
        _deny('INCOMPLETE_CANONICAL_PAIR')
    return tuple(e.event_id for e in graph.events if any(
        w.opening_event_id==opening_event_id and w.closing_event_id==closing_event_id
        for share in e.shares for w in share.weights))
