"""PROD-owned pure reconstruction diagnostics (DOM-PROD-001 XIII.9).

Candidate replay is an observation of surviving sources, never original
membership admission or a substitute for creation visibility evidence.
"""
from dataclasses import dataclass
from datetime import datetime
from app.extensions import db
from app.models import PayrollEvent
from app.services.attendance_service import list_attendance_interval_evidence, elapsed_attendance_seconds
from app.utils.canonical_temporal_resolver import ensure_utc


class HistoricalAssessmentDenied(ValueError):
    pass


@dataclass(frozen=True)
class HistoricalRuleDescriptor:
    version: str
    source_revision: str
    source_path: str
    marker: str | None
    arithmetic_rule: str | None
    record_writer_attribution: str = 'UNAVAILABLE'


CLOSED_RULE = HistoricalRuleDescriptor('closed_sessions:ad9574334:1',
    'ad9574334d72fd92cc93402e851ab0ebc22aaad9',
    'app/services/attendance_service.py;app/services/payroll/pricing.py',
    'closed_sessions', 'divide_first_half_even_28')
LEGACY_RULE = HistoricalRuleDescriptor('open_fragment:bc5c07a2-parent:1',
    'c42f882b8e610d43f355d684a8632d1fa8d50f72', 'app/services/attendance_service.py;app/feats/prod.py',
    None, None)
CURRENT_RULE = HistoricalRuleDescriptor('frozen_pairs:1',
    '81ea0fff5676c90a0bac673956737a7a139202e8',
    'app/services/payroll/pricing.py', 'closed_sessions', 'multiply_first_half_even_28')


@dataclass(frozen=True)
class HistoricalShare:
    policy_locator: str
    credited_seconds: int
    rate_per_minute: str


@dataclass(frozen=True)
class HistoricalEventEvidence:
    event_id: int
    class_id: str
    target_seat_id: int
    actor_seat_id: int
    mechanism: str
    event_type: str
    correlation_id: str
    command_key: str
    recorded_at: object
    rule: HistoricalRuleDescriptor
    candidate_sources: tuple
    pricing_inputs: tuple
    replay_consistency: str
    membership_completeness: str
    pricing_provenance: str
    reasons: tuple


@dataclass(frozen=True)
class HistoricalBusinessEvidence:
    class_id: str
    target_seat_id: int
    source_ids: tuple
    intervals: tuple
    events: tuple
    has_more: bool
    source_visibility: str = 'UNAVAILABLE'


def _scope(ctx, class_id, target_seat_id):
    if (not class_id or not getattr(ctx,'seat_id',None) or not getattr(ctx,'user_id',None)
            or getattr(ctx, 'class_id', None) != class_id
            or getattr(ctx, 'actor_role', None) != 'teacher'
            or type(target_seat_id) is not int or target_seat_id <= 0):
        raise HistoricalAssessmentDenied('UNAUTHORIZED_SCOPE')


def _setting_for(settings, instant):
    available = [s for s in settings if ensure_utc(s.effective_at) <= instant]
    if not available:
        if not settings:
            return None
        rank = (ensure_utc(settings[0].effective_at), ensure_utc(settings[0].created_at))
        first = [s for s in settings if (ensure_utc(s.effective_at),ensure_utc(s.created_at)) == rank]
        return first[0] if len(first)==1 else None
    rank = max((ensure_utc(s.effective_at), ensure_utc(s.created_at)) for s in available)
    winners = [s for s in available if (ensure_utc(s.effective_at), ensure_utc(s.created_at)) == rank]
    return winners[0] if len(winners) == 1 else None


def get_historical_attendance_business_evidence(*, ctx, class_id, target_seat_id,
        setting_inputs=(), payroll_event_ids=None, limit=50, source_limit=2000,
        event_limit=1000, as_of_utc=None):
    """Bound the full source set before pairing, then paginate observations only."""
    _scope(ctx, class_id, target_seat_id)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise HistoricalAssessmentDenied('INVALID_INPUT')
    if (type(source_limit) is not int or not 1 <= source_limit <= 2000
            or type(event_limit) is not int or not 1 <= event_limit <= 1000):
        raise HistoricalAssessmentDenied('INVALID_INPUT')
    if payroll_event_ids is not None and not isinstance(payroll_event_ids, (tuple,list)):
        raise HistoricalAssessmentDenied('INVALID_INPUT')
    if len(setting_inputs)>500:
        raise HistoricalAssessmentDenied('EVIDENCE_LIMIT_EXCEEDED')
    requested = None if payroll_event_ids is None else tuple(payroll_event_ids)
    if requested is not None and (len(requested) > 100 or len(set(requested)) != len(requested)
            or any(type(i) is not int or i <= 0 for i in requested)):
        raise HistoricalAssessmentDenied('INVALID_INPUT')
    if any(s.class_id != class_id for s in setting_inputs):
        raise HistoricalAssessmentDenied('UNAUTHORIZED_SCOPE')
    with db.session.no_autoflush:
        events = PayrollEvent.query.filter_by(class_id=class_id, target_seat_id=target_seat_id).order_by(
            PayrollEvent.recorded_at.asc(), PayrollEvent.id.asc()).limit(event_limit + 1).all()
        if len(events) > event_limit:
            raise HistoricalAssessmentDenied('EVIDENCE_LIMIT_EXCEEDED')
        try:
            rows, intervals = list_attendance_interval_evidence(target_seat_id, class_id,
                ctx=ctx, as_of_utc=as_of_utc, source_limit=source_limit)
        except ValueError as exc:
            if str(exc) == 'EVIDENCE_LIMIT_EXCEEDED':
                raise HistoricalAssessmentDenied('EVIDENCE_LIMIT_EXCEEDED') from None
            raise
    known = {e.id for e in events}
    if requested is not None and not set(requested) <= known:
        raise HistoricalAssessmentDenied('UNAUTHORIZED_SCOPE')
    selected = [e for e in events if requested is None or e.id in requested]
    settings = tuple(sorted(setting_inputs, key=lambda s: (ensure_utc(s.effective_at), ensure_utc(s.created_at))))
    results = []
    for event in selected[:limit]:
        summary = event.summary_json if isinstance(event.summary_json, dict) else {}
        frozen = type(summary.get('allocation_version')) is int and summary.get('allocation_version') == 1
        rule = CURRENT_RULE if frozen else CLOSED_RULE if summary.get('settlement_rule') == 'closed_sessions' else LEGACY_RULE
        at = ensure_utc(event.recorded_at)
        prior = [e for e in events if e.payroll_event_type == 'payroll' and ensure_utc(e.recorded_at) < at]
        tied = [e for e in events if e.payroll_event_type == 'payroll' and ensure_utc(e.recorded_at) == at]
        cutoff = max((ensure_utc(e.recorded_at) for e in prior), default=None)
        legacy = [ensure_utc(e.recorded_at) for e in prior if not isinstance(e.summary_json,dict) or e.summary_json.get('settlement_rule') != 'closed_sessions']
        candidates = []
        groups = {}
        reasons = ['SOURCE_CREATION_VISIBILITY_UNAVAILABLE', 'ORIGINAL_WRITER_ATTRIBUTION_UNAVAILABLE']
        for interval in intervals:
            if interval.closing_event_id is None or interval.closed_at > at or (cutoff and interval.closed_at <= cutoff):
                continue
            start = interval.opened_at
            clips = [t for t in legacy if start < t < interval.closed_at]
            if clips:
                start = max(clips)
                reasons.append('LEGACY_FRAGMENT_REQUIRES_ATTRIBUTION')
            # Preserve canonical IDs but explicitly label any candidate clipped duration.
            seconds = elapsed_attendance_seconds(ctx, [(start, interval.closed_at)])
            candidates.append((interval.opening_event_id, interval.closing_event_id, seconds,
                ensure_utc(start).isoformat(), ensure_utc(interval.closed_at).isoformat()))
            setting = _setting_for(settings, ensure_utc(interval.closed_at))
            if setting is None:
                reasons.append('MISSING_OR_AMBIGUOUS_SETTING')
            else:
                if ensure_utc(setting.created_at) > at:
                    reasons.append('SETTING_NOT_VISIBLE_AT_PAYMENT')
                key = (setting.policy_locator, setting.rate_per_minute)
                groups[key] = groups.get(key, 0) + seconds
        shares = summary.get('pricing')
        pricing, consistency = [], 'UNAVAILABLE'
        pricing_status = 'UNAVAILABLE'
        if isinstance(shares, list) and shares:
            try:
                for share in shares:
                    if (not isinstance(share, dict) or type(share['seconds']) is not int
                            or share['seconds'] < 0 or not isinstance(share['policy_uuid'], str)
                            or not isinstance(share['pay_rate_per_minute'], str)):
                        raise ValueError
                    pricing.append(HistoricalShare(share['policy_uuid'], share['seconds'], share['pay_rate_per_minute']))
                # Decimal equality is monetary territory: strings are retained unchanged,
                # policy+seconds match is a PROD business consistency conclusion only.
                consistency = 'MATCH' if sorted((p.policy_locator,p.credited_seconds) for p in pricing) == sorted((p,s) for (p,_),s in groups.items()) else 'MISMATCH'
                if 'MISSING_OR_AMBIGUOUS_SETTING' in reasons or 'SETTING_NOT_VISIBLE_AT_PAYMENT' in reasons:
                    consistency = 'UNAVAILABLE'
                pricing_status = 'RECORDED_INPUTS_ONLY'
                if len({p.policy_locator for p in pricing}) != len(pricing):
                    consistency = 'MISMATCH'; reasons.append('DUPLICATE_SETTING_SHARE')
                if frozen:
                    sources = [source for share in shares for source in share.get('intervals', ())]
                    if any(not isinstance(source,dict)
                            or any(type(source[field]) is not int or source[field]<=0 for field in ('opening_event_id','closing_event_id'))
                            or type(source['credited_seconds']) is not int or source['credited_seconds']<0
                            for source in sources):
                        raise ValueError('Malformed source identity or duration')
                    for share in shares:
                        members = share.get('intervals', ())
                        if sum(source['credited_seconds'] for source in members) != share['seconds']:
                            consistency = 'MISMATCH'; reasons.append('RECORDED_SHARE_MEMBERSHIP_MISMATCH')
                        for source in members:
                            closed = ensure_utc(datetime.fromisoformat(source['closing_timestamp']))
                            governed = _setting_for(settings, closed)
                            if governed is None or governed.policy_locator != share['policy_uuid']:
                                consistency = 'MISMATCH'; reasons.append('RECORDED_SHARE_MEMBERSHIP_MISMATCH')
                    canonical = {(i.opening_event_id,i.closing_event_id): i.as_evidence() for i in intervals if i.closing_event_id is not None}
                    if (len(sources) != len(candidates) or len({(s['opening_event_id'],s['closing_event_id']) for s in sources}) != len(sources)
                            or any(canonical.get((s['opening_event_id'],s['closing_event_id'])) != s for s in sources)
                            or {(s['opening_event_id'],s['closing_event_id']) for s in sources} != {(c[0],c[1]) for c in candidates}):
                        consistency = 'MISMATCH'; reasons.append('RECORDED_MEMBERSHIP_MISMATCH')
            except (KeyError, TypeError, ValueError):
                pricing = []; consistency = 'UNAVAILABLE'; reasons.append('MALFORMED_PRICING')
        elif rule is CLOSED_RULE and groups and not any(r in {'MISSING_OR_AMBIGUOUS_SETTING','SETTING_NOT_VISIBLE_AT_PAYMENT'} for r in reasons):
            pricing = [HistoricalShare(p,s,r) for (p,r),s in groups.items()]
            pricing_status = 'RETAINED_CONFIGURATION_CANDIDATE'
        else:
            reasons.append('ORIGINAL_PRICING_UNAVAILABLE')
        if len(tied) > 1:
            consistency = 'UNAVAILABLE'; reasons.append('TIED_PAYROLL_BOUNDARY')
        if rule is LEGACY_RULE or event.payroll_event_type != 'payroll':
            candidates = []; pricing = []; consistency = 'UNAVAILABLE'
            reasons.append('FRAGMENT_OR_MANUAL_ATTRIBUTION_NOT_ADMITTED')
        results.append(HistoricalEventEvidence(event.id,class_id,target_seat_id,event.actor_seat_id,
            event.mechanism,event.payroll_event_type,event.correlation_id,event.idempotency_key,event.recorded_at,
            rule,tuple(candidates),tuple(pricing),consistency,'UNAVAILABLE',pricing_status,tuple(dict.fromkeys(reasons))))
    return HistoricalBusinessEvidence(class_id,target_seat_id,tuple(r.id for r in rows),tuple(intervals),
        tuple(results),len(selected)>limit)
