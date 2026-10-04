"""FEAT-PROD-005 and PROD-003 recovery: pure previews, one atomic command.

Authority: DOM-PROD-001 VIII/XI, FEAT-PROD-005 V–VIII, SPEC-PROD-001.
Owning-domain conclusions and Operations proofs are composed only here.
"""
from dataclasses import dataclass
from flask import current_app
from itsdangerous import URLSafeSerializer, BadSignature
from hashlib import sha256
import json

from app.feats.base import FEATContext, audit_protected
from app.services.attendance_invalidation_service import (
    AttendanceCorrectionDenied, REASONS, interval_eligibility, invalidation_for_command,
    record_interval_invalidation, record_payroll_business_correction,
    payroll_event_for_recovery, payroll_recovery_for_command, record_payroll_business_recovery,
)
from app.services.identity_service import resolve_teacher_target_seat
from app.services.class_configuration_query_service import verify_teacher_owns_class, get_banking_directive
from app.services.ledger_balance_query_service import get_account_posting_boundary
from app.services.ledger_payroll_allocation import payroll_allocation_proof, get_payroll_credit_evidence_records
from app.services.ledger_recovery_service import (
    RecoveryIntegrityError, ledger_origin_locator, lock_recovery_scope,
    get_credit_compensation_proof, get_credit_recovery_evidence_records,
    resolve_credit_recovery, apply_credit_recovery, resolve_payroll_credit_locator,
    get_recovery_outcome_records, get_recovery_outcome,
)
from app.services.ledger_evidence import LedgerCreationEvidence
from app.utils.audit_verifier import verified_creation_evidence, verify_record_creation_lineage, PROTECTED_FIELDS_BY_TABLE
from app.utils.canonical_temporal_resolver import canonical_temporal_resolver, CLASS_LEVEL_EVALUATION


@dataclass(frozen=True)
class CorrectionPreview:
    identity: str
    disposition: str
    eligibility: object | None
    original: object | None
    plan: object | None
    material: dict

    def public(self):
        plan = self.plan
        funding = plan.resolved_plan if plan else None
        return {'expected_preview_identity': self.identity, 'disposition': self.disposition,
            'credited_seconds': self.eligibility.interval.credited_seconds if self.eligibility else None,
            'recovery_cents': plan.allocated_cents if plan else 0,
            'protection_transfer': str(funding.recovery_transfer_amount) if funding else None,
            'checking_after': str(funding.checking_after) if funding else None,
            'savings_after': str(funding.savings_after) if funding else None,
            'original_payroll_event_id': self.original.id if self.original else None,
            'recovery_kind': plan.recovery_kind if plan else None}


def _digest(material):
    return sha256(json.dumps(material, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()


def _preview_identity(material):
    return URLSafeSerializer(current_app.secret_key, salt='attendance-correction-preview-v1').dumps({'version':1, 'digest':_digest(material)})


def _validate_preview_identity(identity):
    try:
        payload = URLSafeSerializer(current_app.secret_key, salt='attendance-correction-preview-v1').loads(identity)
        if set(payload) != {'version','digest'} or payload['version'] != 1 or not isinstance(payload['digest'], str):
            raise ValueError
    except (BadSignature, TypeError, ValueError):
        raise AttendanceCorrectionDenied('PREVIEW_CHANGED') from None


def _lock_original(ctx, original):
    locator = resolve_payroll_credit_locator(class_id=ctx.class_id, target_seat_id=original.target_seat_id,
        correlation_id=original.correlation_id, idempotency_key=original.idempotency_key,
        originating_actor_seat_id=original.actor_seat_id, originating_mechanism=original.mechanism,
        original_event_type=original.payroll_event_type)
    if locator is None:
        raise AttendanceCorrectionDenied('PROVENANCE_UNAVAILABLE')
    lock_recovery_scope(ctx.class_id, original.target_seat_id, locator)


def _authorize(ctx, target):
    try:
        resolve_teacher_target_seat(ctx=ctx, target_seat_id=target)
    except ValueError:
        raise AttendanceCorrectionDenied('UNAUTHORIZED_SCOPE') from None
    if verify_teacher_owns_class(ctx.class_id, ctx.user_id) is None:
        raise AttendanceCorrectionDenied('UNAUTHORIZED_SCOPE')


def ledger_creation_proofs(records, class_id):
    """Map genuine Operations query results to immutable Ledger proof inputs."""
    result = []
    for record in records:
        proof = verified_creation_evidence('ledger_transaction', record, class_id)
        if proof is not None:
            result.append(LedgerCreationEvidence(proof.table_name, proof.row_pk, proof.class_id,
                proof.lineage_event_id, proof.lineage_token, proof.signature_version,
                proof.protected_fields, proof.protected_values))
    return tuple(result)


def _credit_proof(ctx, original):
    if not verify_record_creation_lineage('payroll_event', original, ctx.class_id):
        raise AttendanceCorrectionDenied('PROVENANCE_UNAVAILABLE')
    locator = resolve_payroll_credit_locator(class_id=ctx.class_id, target_seat_id=original.target_seat_id,
        correlation_id=original.correlation_id, idempotency_key=original.idempotency_key,
        originating_actor_seat_id=original.actor_seat_id, originating_mechanism=original.mechanism,
        original_event_type=original.payroll_event_type)
    if locator is None:
        raise AttendanceCorrectionDenied('PROVENANCE_UNAVAILABLE')
    records = get_credit_recovery_evidence_records(class_id=ctx.class_id,
        target_seat_id=original.target_seat_id, origin_locator=locator)
    evidence = ledger_creation_proofs(records, ctx.class_id)
    proof = get_credit_compensation_proof(class_id=ctx.class_id, target_seat_id=original.target_seat_id,
        origin_locator=locator, through_posting_sequence=get_account_posting_boundary(original.target_seat_id, ctx.class_id, 'checking'),
        creation_evidence=evidence)
    if proof.status == 'PENDING':
        raise AttendanceCorrectionDenied('PAYROLL_PENDING')
    if proof.status != 'VERIFIED':
        raise AttendanceCorrectionDenied('PROVENANCE_UNAVAILABLE')
    return proof, evidence


def _intent_locator(kind, material):
    return f'prod-recovery:v1:{kind}:{_digest(material)}'


def preview_attendance_interval_invalidation(*, ctx, target_seat_id, opening_event_id, closing_event_id, reason_code):
    _authorize(ctx, target_seat_id)
    if reason_code not in REASONS:
        raise AttendanceCorrectionDenied('INVALID_REASON')
    eligibility = interval_eligibility(ctx=ctx, target_seat_id=target_seat_id,
        opening_event_id=opening_event_id, closing_event_id=closing_event_id)
    if eligibility.invalidation:
        raise AttendanceCorrectionDenied('ALREADY_INVALIDATED')
    source = {'class_id': ctx.class_id, 'actor_seat_id': ctx.seat_id, 'target_seat_id': target_seat_id,
        'pair': eligibility.interval.as_evidence(), 'reason_code': reason_code,
        'settlement': eligibility.settlement_status}
    original, plan = eligibility.payroll_event, None
    disposition = 'UNPAID'
    if eligibility.settlement_status != 'unpaid':
        if eligibility.settlement_status != 'recorded' or original is None:
            raise AttendanceCorrectionDenied('PROVENANCE_UNAVAILABLE')
        proof, evidence = _credit_proof(ctx, original)
        allocation = payroll_allocation_proof(class_id=ctx.class_id, target_seat_id=target_seat_id,
            correlation_id=original.correlation_id, idempotency_key=original.idempotency_key,
            allocation_version=(original.summary_json or {}).get('allocation_version'), pricing=eligibility.pricing,
            originating_actor_seat_id=original.actor_seat_id, originating_mechanism=original.mechanism,
            through_posting_sequence=get_account_posting_boundary(target_seat_id, ctx.class_id, 'checking'),
            creation_evidence=evidence)
        if allocation['status'] != 'verified':
            raise AttendanceCorrectionDenied('PROVENANCE_UNAVAILABLE')
        source.update(original_event=original.id, original_lineage=(original.lineage_event_id, original.lineage_token, original.lineage_version),
            frozen_pricing=eligibility.pricing, compensation=proof.material)
        allocated = allocation['allocations'][(opening_event_id, closing_event_id)]
        if proof.remaining_cents == 0:
            disposition = 'RECOVERED'
        elif allocated == 0:
            disposition = 'ZERO_CENT'
        else:
            locator = _intent_locator('interval', {'class':ctx.class_id, 'actor':ctx.seat_id, 'target':target_seat_id,
                'opening':opening_event_id, 'closing':closing_event_id, 'reason':reason_code})
            plan = resolve_credit_recovery(proof=proof, recovery_kind='INTERVAL', correction_intent_locator=locator,
                banking_directive=get_banking_directive(ctx.class_id), actor_seat_id=ctx.seat_id, mechanism='teacher',
                allocation_proof=allocation, interval_key=(opening_event_id, closing_event_id))
            source['money_plan'] = plan.material
            disposition = 'PAID'
    return CorrectionPreview(_preview_identity(source), disposition, eligibility, original, plan, source)


def _command_intent(ctx, target, expected, **intent):
    return {'fingerprint_version':1, 'class_id':ctx.class_id, 'actor_seat_id':ctx.seat_id,
        'target_seat_id':target, 'expected_preview_identity':expected, **intent}


def _replay_result(ctx, row, receipt, digest, table):
    if not isinstance(receipt, dict):
        raise AttendanceCorrectionDenied('INTEGRITY_FAILURE')
    if receipt.get('canonical_intent_digest') != digest or receipt.get('fingerprint_version') != 1:
        raise AttendanceCorrectionDenied('REPLAY_MISMATCH')
    if not verify_record_creation_lineage(table, row, ctx.class_id):
        raise AttendanceCorrectionDenied('INTEGRITY_FAILURE')
    locators = receipt.get('opaque_outcome_locators')
    if not isinstance(locators, dict) or not isinstance(receipt.get('original_settlement_disposition'), str):
        raise AttendanceCorrectionDenied('INTEGRITY_FAILURE')
    effects = locators.get('ledger_effects', [])
    records = get_recovery_outcome_records(class_id=ctx.class_id, target_seat_id=row.target_seat_id, effect_locators=effects)
    result = get_recovery_outcome(class_id=ctx.class_id, target_seat_id=row.target_seat_id,
        effect_locators=effects, creation_evidence=ledger_creation_proofs(records, ctx.class_id)) if effects else {'recovered_cents':0}
    return {'status':'accepted', 'replayed':True, 'record_id':row.id, 'recovery_cents':result['recovered_cents'],
        'disposition':receipt['original_settlement_disposition']}


def _acceptance_time(ctx):
    return canonical_temporal_resolver(CLASS_LEVEL_EVALUATION, canonical_execution_context=ctx, primitive='current_time').canonical_now_utc


def invalidate_attendance_interval(*, ctx, target_seat_id, opening_event_id, closing_event_id,
                                   reason_code, idempotency_key, expected_preview_identity):
    _authorize(ctx, target_seat_id)
    if not isinstance(idempotency_key, str) or not idempotency_key.strip() or len(idempotency_key)>128:
        raise ValueError('A nonempty command key of at most 128 characters is required.')
    intent = _command_intent(ctx, target_seat_id, expected_preview_identity,
        opening_event_id=opening_event_id, closing_event_id=closing_event_id, reason_code=reason_code)
    digest = _digest(intent)
    with FEATContext('FEAT-PROD-005', idempotency_key=idempotency_key):
        existing = invalidation_for_command(ctx=ctx, idempotency_key=idempotency_key)
        if existing:
            return _replay_result(ctx, existing, existing.receipt_json, digest, 'attendance_interval_invalidation')
        lock_recovery_scope(ctx.class_id, target_seat_id)
        existing = invalidation_for_command(ctx=ctx, idempotency_key=idempotency_key)
        if existing:
            return _replay_result(ctx, existing, existing.receipt_json, digest, 'attendance_interval_invalidation')
        _validate_preview_identity(expected_preview_identity)
        locked_eligibility = interval_eligibility(ctx=ctx, target_seat_id=target_seat_id,
            opening_event_id=opening_event_id, closing_event_id=closing_event_id)
        if locked_eligibility.payroll_event is not None:
            _lock_original(ctx, locked_eligibility.payroll_event)
        preview = preview_attendance_interval_invalidation(ctx=ctx, target_seat_id=target_seat_id,
            opening_event_id=opening_event_id, closing_event_id=closing_event_id, reason_code=reason_code)
        if preview.identity != expected_preview_identity:
            raise AttendanceCorrectionDenied('PREVIEW_CHANGED')
        result = apply_credit_recovery(plan=preview.plan, idempotency_key=idempotency_key) if preview.plan else None
        locators = {}
        if result:
            locators = {'ledger_origin':result['origin_locator'], 'ledger_effects':list(result['effect_locators']),
                'correction_intent':preview.plan.correction_intent_locator}
        if preview.original:
            locators['original_payroll_event'] = f'prod-payroll:v1:{preview.original.id}'
        receipt = {'expected_preview_identity':expected_preview_identity, 'fingerprint_version':1,
            'canonical_intent_digest':digest, 'original_settlement_disposition':preview.disposition,
            'opaque_outcome_locators':locators}
        accepted_at = _acceptance_time(ctx)
        decision = record_interval_invalidation(ctx=ctx, target_seat_id=target_seat_id,
            opening_event_id=opening_event_id, closing_event_id=closing_event_id, reason_code=reason_code,
            idempotency_key=idempotency_key, recorded_at=accepted_at, receipt=receipt)
        audit_protected('attendance_interval_invalidation', decision, 'INSERT', PROTECTED_FIELDS_BY_TABLE['attendance_interval_invalidation'])
        if result and result['principal_locator']:
            event = record_payroll_business_correction(ctx=ctx, original=preview.original,
                correction_intent='INTERVAL_INVALIDATION', correction_intent_locator=preview.plan.correction_intent_locator,
                invalidation_id=decision.id, opening_event_id=opening_event_id, closing_event_id=closing_event_id,
                ledger_origin_locator=result['origin_locator'], ledger_result_locator=result['principal_locator'], recorded_at=accepted_at)
            audit_protected('payroll_event', event, 'INSERT', PROTECTED_FIELDS_BY_TABLE['payroll_event'])
        return {'status':'accepted', 'replayed':False, 'record_id':decision.id,
            'recovery_cents':preview.plan.allocated_cents if preview.plan else 0, 'disposition':preview.disposition}


def preview_payroll_recovery(*, ctx, payroll_event_id):
    original = payroll_event_for_recovery(ctx=ctx, payroll_event_id=payroll_event_id)
    _authorize(ctx, original.target_seat_id)
    proof, _evidence = _credit_proof(ctx, original)
    if proof.remaining_cents == 0:
        raise AttendanceCorrectionDenied('ALREADY_RECOVERED')
    kind = 'EXACT_REVERSAL' if proof.recovered_cents == 0 else 'RESIDUAL'
    locator = _intent_locator('payment', {'class':ctx.class_id, 'actor':ctx.seat_id, 'event':original.id})
    plan = resolve_credit_recovery(proof=proof, recovery_kind=kind, correction_intent_locator=locator,
        banking_directive=get_banking_directive(ctx.class_id), actor_seat_id=ctx.seat_id, mechanism='teacher')
    material = {'class':ctx.class_id, 'actor':ctx.seat_id, 'target':original.target_seat_id,
        'original_event':original.id, 'original_lineage':(original.lineage_event_id, original.lineage_token, original.lineage_version),
        'money_plan':plan.material}
    return CorrectionPreview(_preview_identity(material), kind, None, original, plan, material)


def recover_payroll_payment(*, ctx, payroll_event_id, idempotency_key, expected_preview_identity):
    if not isinstance(idempotency_key, str) or not idempotency_key.strip() or len(idempotency_key)>128:
        raise ValueError('A nonempty command key of at most 128 characters is required.')
    original = payroll_event_for_recovery(ctx=ctx, payroll_event_id=payroll_event_id)
    _authorize(ctx, original.target_seat_id)
    digest = _digest(_command_intent(ctx, original.target_seat_id, expected_preview_identity, payroll_event_id=payroll_event_id))
    with FEATContext('FEAT-PROD-003', idempotency_key=idempotency_key):
        existing = payroll_recovery_for_command(ctx=ctx, idempotency_key=idempotency_key)
        if existing:
            return _replay_result(ctx, existing, (existing.summary_json or {}).get('command_receipt', {}), digest, 'payroll_event')
        lock_recovery_scope(ctx.class_id, original.target_seat_id)
        existing = payroll_recovery_for_command(ctx=ctx, idempotency_key=idempotency_key)
        if existing:
            return _replay_result(ctx, existing, (existing.summary_json or {}).get('command_receipt', {}), digest, 'payroll_event')
        _validate_preview_identity(expected_preview_identity)
        _lock_original(ctx, original)
        preview = preview_payroll_recovery(ctx=ctx, payroll_event_id=payroll_event_id)
        if preview.identity != expected_preview_identity:
            raise AttendanceCorrectionDenied('PREVIEW_CHANGED')
        result = apply_credit_recovery(plan=preview.plan, idempotency_key=idempotency_key)
        receipt = {'expected_preview_identity':expected_preview_identity, 'fingerprint_version':1, 'canonical_intent_digest':digest,
            'original_settlement_disposition':preview.disposition, 'opaque_outcome_locators':{
                'ledger_effects':list(result['effect_locators']), 'ledger_origin':result['origin_locator'],
                'correction_intent':preview.plan.correction_intent_locator}}
        event = record_payroll_business_recovery(ctx=ctx, original=original, recovery_kind=preview.plan.recovery_kind,
            idempotency_key=idempotency_key, recorded_at=_acceptance_time(ctx), receipt=receipt,
            correction_intent_locator=preview.plan.correction_intent_locator, ledger_result_locator=result['principal_locator'])
        audit_protected('payroll_event', event, 'INSERT', PROTECTED_FIELDS_BY_TABLE['payroll_event'])
        return {'status':'accepted', 'replayed':False, 'record_id':event.id,
            'recovery_cents':preview.plan.allocated_cents, 'disposition':preview.disposition}
