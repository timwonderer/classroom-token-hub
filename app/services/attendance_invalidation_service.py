"""PROD-owned terminal eligibility and business records (DOM-PROD-001 XI.4).

No monetary or foreign-domain queries belong here. The FEAT supplies proven
opaque outcomes and emits Operations evidence in the creating transaction.
"""
from dataclasses import dataclass
import re

from app.extensions import db
from app.models import AttendanceIntervalInvalidation, PayrollEvent
from app.services.attendance_service import list_attendance_intervals
from app.services.payroll_interval_provenance import payroll_interval_memberships
from app.feats.base import get_active_feat_name, get_correlation_id

REASONS = frozenset({'INVALID_ATTENDANCE', 'NON_WORK_ACTIVITY', 'DUPLICATE_PARTICIPATION'})
RECEIPT_FIELDS = frozenset({'expected_preview_identity', 'fingerprint_version', 'canonical_intent_digest', 'original_settlement_disposition', 'opaque_outcome_locators'})


class AttendanceCorrectionDenied(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class IntervalEligibility:
    interval: object
    invalidation: object | None
    settlement_status: str
    payroll_event: object | None
    pricing: object | None
    requires_reconstruction: bool = False


def _scope(ctx, target_seat_id):
    if not ctx or ctx.actor_role != 'teacher' or not ctx.class_id or not ctx.seat_id or not target_seat_id:
        raise AttendanceCorrectionDenied('UNAUTHORIZED_SCOPE')


def invalidation_for_command(*, ctx, idempotency_key):
    return AttendanceIntervalInvalidation.query.filter_by(class_id=ctx.class_id, idempotency_key=idempotency_key).first()


def interval_eligibility(*, ctx, target_seat_id, opening_event_id, closing_event_id):
    _scope(ctx, target_seat_id)
    interval = next((i for i in list_attendance_intervals(target_seat_id, ctx.class_id, ctx=ctx)
        if i.opening_event_id == opening_event_id and i.closing_event_id == closing_event_id
        and i.closing_event_id is not None), None)
    if interval is None:
        raise AttendanceCorrectionDenied('INCOMPLETE_INTERVAL')
    decision = AttendanceIntervalInvalidation.query.filter_by(class_id=ctx.class_id, target_seat_id=target_seat_id,
        opening_event_id=opening_event_id, closing_event_id=closing_event_id).first()
    membership = payroll_interval_memberships(target_seat_id, ctx.class_id, ctx=ctx).get((opening_event_id, closing_event_id))
    if membership is None:
        raise AttendanceCorrectionDenied('INCOMPLETE_INTERVAL')
    return IntervalEligibility(interval, decision, membership['status'], membership.get('event'), membership.get('pricing'),
        membership.get('requires_reconstruction',False))


def _validate_receipt(receipt):
    if (not isinstance(receipt, dict) or set(receipt) != RECEIPT_FIELDS
        or type(receipt['fingerprint_version']) is not int or receipt['fingerprint_version'] != 1
        or not isinstance(receipt['expected_preview_identity'],str) or not receipt['expected_preview_identity']
        or not isinstance(receipt['canonical_intent_digest'],str)
        or re.fullmatch(r'[a-f0-9]{64}',receipt['canonical_intent_digest']) is None
        or receipt['original_settlement_disposition'] not in {'UNPAID','PAID','RECOVERED','ZERO_CENT','EXACT_REVERSAL','RESIDUAL'}
        or not isinstance(receipt['opaque_outcome_locators'],dict)):
        raise ValueError('Invalid nonmonetary command receipt.')
    patterns={'ledger_origin':r'ledger-credit:v1:[1-9][0-9]*','ledger_effects':r'ledger-effect:v1:[1-9][0-9]*',
        'correction_intent':r'prod-recovery:v1:(?:interval|payment):[a-f0-9]{64}',
        'original_payroll_event':r'prod-payroll:v1:[1-9][0-9]*',
        'ledger_origins':r'ledger-credit:v1:[1-9][0-9]*',
        'original_payroll_events':r'prod-payroll:v1:[1-9][0-9]*'}
    for key,value in receipt['opaque_outcome_locators'].items():
        if key not in patterns:
            raise ValueError('Invalid nonmonetary command receipt.')
        list_keys={'ledger_effects','ledger_origins','original_payroll_events'}
        values=value if key in list_keys and isinstance(value,list) else [value] if key not in list_keys else [None]
        if key in list_keys and isinstance(value,list) and (len(set(value)) != len(value) if all(isinstance(v,str) for v in value) else True):
            raise ValueError('Duplicate opaque outcome locator.')
        if any(not isinstance(item,str) or re.fullmatch(patterns[key],item) is None for item in values):
            raise ValueError('Invalid opaque outcome locator.')


def _original_anchor(ctx,original):
    if not isinstance(original,PayrollEvent):
        raise AttendanceCorrectionDenied('UNAUTHORIZED_SCOPE')
    _scope(ctx, original.target_seat_id)
    stored=PayrollEvent.query.filter_by(id=original.id,class_id=ctx.class_id,target_seat_id=original.target_seat_id).first()
    if stored is None or stored is not original or stored.payroll_event_type not in {'payroll','manual_credit'}:
        raise AttendanceCorrectionDenied('UNAUTHORIZED_SCOPE')
    return stored


def _recovery_locators(intent,result,origin=None):
    if (not isinstance(intent,str) or re.fullmatch(r'prod-recovery:v1:(?:interval|payment):[a-f0-9]{64}',intent) is None
        or not isinstance(result,str) or re.fullmatch(r'ledger-effect:v1:[1-9][0-9]*',result) is None
        or (origin is not None and (not isinstance(origin,str) or re.fullmatch(r'ledger-credit:v1:[1-9][0-9]*',origin) is None))):
        raise AttendanceCorrectionDenied('INTEGRITY_FAILURE')


def record_interval_invalidation(*, ctx, target_seat_id, opening_event_id, closing_event_id,
                                reason_code, idempotency_key, recorded_at, receipt, reconstruction_graph=None):
    """Append one complete immutable terminal decision inside FEAT-PROD-005."""
    if get_active_feat_name() != 'FEAT-PROD-005':
        raise ValueError('Attendance invalidation requires FEAT-PROD-005.')
    eligibility = interval_eligibility(ctx=ctx, target_seat_id=target_seat_id,
        opening_event_id=opening_event_id, closing_event_id=closing_event_id)
    if eligibility.invalidation:
        raise AttendanceCorrectionDenied('ALREADY_INVALIDATED')
    if reason_code not in REASONS:
        raise AttendanceCorrectionDenied('INVALID_REASON')
    _validate_receipt(receipt)
    disposition=receipt['original_settlement_disposition']
    outcomes=receipt['opaque_outcome_locators']
    if reconstruction_graph is not None:
        from app.services.historical_payroll_reconstruction import reconstructed_pair_events
        members = reconstructed_pair_events(reconstruction_graph,ctx=ctx,target_seat_id=target_seat_id,
            opening_event_id=opening_event_id,closing_event_id=closing_event_id)
        if (not members or disposition not in {'PAID','RECOVERED','ZERO_CENT'}
                or outcomes.get('original_payroll_event') not in {f'prod-payroll:v1:{i}' for i in members}):
            raise AttendanceCorrectionDenied('INTEGRITY_FAILURE')
    elif eligibility.settlement_status == 'unpaid':
        if disposition != 'UNPAID' or outcomes:
            raise AttendanceCorrectionDenied('INTEGRITY_FAILURE')
    elif eligibility.settlement_status == 'recorded' and eligibility.payroll_event is not None:
        if (disposition not in {'PAID','RECOVERED','ZERO_CENT'}
            or outcomes.get('original_payroll_event') != f'prod-payroll:v1:{eligibility.payroll_event.id}'):
            raise AttendanceCorrectionDenied('INTEGRITY_FAILURE')
    else:
        raise AttendanceCorrectionDenied('PROVENANCE_UNAVAILABLE')
    row = AttendanceIntervalInvalidation(class_id=ctx.class_id, actor_seat_id=ctx.seat_id,
        target_seat_id=target_seat_id, opening_event_id=opening_event_id, closing_event_id=closing_event_id,
        reason_code=reason_code, idempotency_key=idempotency_key, correlation_id=get_correlation_id(),
        recorded_at=recorded_at, receipt_json=receipt)
    db.session.add(row)
    db.session.flush()
    return row


def record_payroll_business_correction(*, ctx, original, correction_intent, correction_intent_locator,
                                       invalidation_id=None, opening_event_id=None, closing_event_id=None, ledger_origin_locator=None, ledger_result_locator, recorded_at, reconstruction_graph=None):
    """PROD-only correction writer; amounts and effects are supplied by no caller."""
    if get_active_feat_name() not in {'FEAT-PROD-005', 'FEAT-PROD-003'}:
        raise ValueError('Payroll correction requires its declared FEAT.')
    _original_anchor(ctx,original)
    if original.class_id != ctx.class_id or correction_intent not in {'INTERVAL_INVALIDATION', 'RESIDUAL_RECOVERY'}:
        raise AttendanceCorrectionDenied('UNAUTHORIZED_SCOPE')
    _original_anchor(ctx,original)
    _recovery_locators(correction_intent_locator,ledger_result_locator,ledger_origin_locator)
    if correction_intent == 'INTERVAL_INVALIDATION':
        decision=AttendanceIntervalInvalidation.query.filter_by(id=invalidation_id,class_id=ctx.class_id,
            target_seat_id=original.target_seat_id,opening_event_id=opening_event_id,closing_event_id=closing_event_id).first()
        membership=payroll_interval_memberships(original.target_seat_id,ctx.class_id,ctx=ctx).get((opening_event_id,closing_event_id),{})
        admitted = (original.payroll_event_type == 'payroll' and membership.get('status') == 'recorded'
            and membership.get('event') is original)
        if reconstruction_graph is not None:
            from app.services.historical_payroll_reconstruction import reconstructed_pair_events
            admitted = original.id in reconstructed_pair_events(reconstruction_graph,ctx=ctx,
                target_seat_id=original.target_seat_id,opening_event_id=opening_event_id,closing_event_id=closing_event_id)
        if decision is None or not admitted or ledger_origin_locator is None:
            raise AttendanceCorrectionDenied('INTEGRITY_FAILURE')
    summary = {'original_payroll_event_id': original.id, 'correction_intent': correction_intent,
        'correction_intent_locator': correction_intent_locator, 'ledger_result_locator': ledger_result_locator}
    if invalidation_id is not None:
        summary.update(invalidation_id=invalidation_id, opening_event_id=opening_event_id,
            closing_event_id=closing_event_id, ledger_origin_locator=ledger_origin_locator)
    row = PayrollEvent(class_id=ctx.class_id, actor_seat_id=ctx.seat_id, target_seat_id=original.target_seat_id,
        correlation_id=get_correlation_id(), idempotency_key=correction_intent_locator,
        policy_uuid=original.policy_uuid, mechanism='TEACHER', payroll_event_type='correction',
        recorded_at=recorded_at, payroll_cycle_id=original.payroll_cycle_id, summary_json=summary)
    db.session.add(row)
    db.session.flush()
    return row


def payroll_event_for_recovery(*, ctx, payroll_event_id):
    row = PayrollEvent.query.filter_by(class_id=ctx.class_id, id=payroll_event_id).first()
    if row is None or row.payroll_event_type not in {'payroll', 'manual_credit'}:
        raise AttendanceCorrectionDenied('PROVENANCE_UNAVAILABLE')
    _scope(ctx, row.target_seat_id)
    return row


def payroll_recovery_for_command(*, ctx, idempotency_key):
    rows = PayrollEvent.query.filter(PayrollEvent.class_id == ctx.class_id,
        PayrollEvent.idempotency_key == idempotency_key,
        PayrollEvent.payroll_event_type.in_(['reversal', 'correction'])).all()
    return next((row for row in rows if isinstance(row.summary_json, dict) and 'command_receipt' in row.summary_json), None)


def record_payroll_business_recovery(*, ctx, original, recovery_kind, idempotency_key,
                                    recorded_at, receipt, correction_intent_locator, ledger_result_locator):
    if get_active_feat_name() != 'FEAT-PROD-003':
        raise ValueError('Payment recovery requires FEAT-PROD-003.')
    _original_anchor(ctx,original)
    if original.class_id != ctx.class_id or recovery_kind not in {'EXACT_REVERSAL', 'RESIDUAL'}:
        raise AttendanceCorrectionDenied('UNAUTHORIZED_SCOPE')
    _original_anchor(ctx,original)
    _validate_receipt(receipt)
    _recovery_locators(correction_intent_locator,ledger_result_locator)
    outcomes=receipt['opaque_outcome_locators']
    if (outcomes.get('correction_intent') != correction_intent_locator or ledger_result_locator not in outcomes.get('ledger_effects',[])
        or not outcomes.get('ledger_origin') or receipt['original_settlement_disposition'] != recovery_kind):
        raise AttendanceCorrectionDenied('INTEGRITY_FAILURE')
    summary = {'original_payroll_event_id': original.id, 'correction_intent_locator': correction_intent_locator,
        'ledger_result_locator': ledger_result_locator, 'command_receipt': receipt}
    if recovery_kind == 'RESIDUAL':
        summary['correction_intent'] = 'RESIDUAL_RECOVERY'
    row = PayrollEvent(class_id=ctx.class_id, actor_seat_id=ctx.seat_id, target_seat_id=original.target_seat_id,
        correlation_id=original.correlation_id if recovery_kind == 'EXACT_REVERSAL' else get_correlation_id(),
        idempotency_key=idempotency_key, policy_uuid=original.policy_uuid, mechanism='TEACHER',
        payroll_event_type='reversal' if recovery_kind == 'EXACT_REVERSAL' else 'correction',
        recorded_at=recorded_at, payroll_cycle_id=original.payroll_cycle_id, summary_json=summary)
    db.session.add(row)
    db.session.flush()
    return row
