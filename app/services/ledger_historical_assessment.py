"""Ledger-owned historical arithmetic/identity observations (DOM-LED-001 IX.2).

None means unavailable, never zero. These observations cannot execute recovery.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
from app.extensions import db
from app.models import Transaction
from app.services.ledger_evidence import evidence_matches
from app.services.ledger_recovery_service import ledger_origin_locator


@dataclass(frozen=True)
class HistoricalLedgerRecord:
    """Immutable source-only Ledger projection for FEAT/Operations diagnostics."""
    values: tuple

    def __getattr__(self, name):
        for field, value in self.values:
            if field == name:
                return value
        raise AttributeError(name)


_SOURCE_FIELDS = (
    'id','class_id','actor_seat_id','target_seat_id','mechanism','amount_cents',
    'timestamp','account_type','description','correlation_id','feat_code',
    'idempotency_key','policy_id','type','posting_sequence','command_reservation_id',
    'compensation_origin_locator','compensation_amount_cents','correction_intent_locator',
    'seat_id','amount','original_transaction_id','lineage_event_id','lineage_token','lineage_version',
)


@dataclass(frozen=True)
class HistoricalPricingInput:
    policy_locator: str
    credited_seconds: int
    rate_per_minute: str


@dataclass(frozen=True)
class HistoricalPayrollMoneyInput:
    class_id: str
    target_seat_id: int
    actor_seat_id: int
    mechanism: str
    event_type: str
    correlation_id: str
    command_key: str
    arithmetic_rule: str | None
    pricing_inputs: tuple


@dataclass(frozen=True)
class HistoricalMoneyAssessment:
    credit_identity: str
    credit_locator: str | None
    observed_credit_cents: int | None
    replay_cents: int | None
    arithmetic_comparison: str
    compensation_completeness: str
    recovered_cents: int | None
    current_execution_eligibility: str
    reasons: tuple


def _scope(ctx, class_id, target_seat_id):
    if (not class_id or not getattr(ctx,'seat_id',None) or not getattr(ctx,'user_id',None)
            or getattr(ctx, 'class_id', None) != class_id
            or getattr(ctx, 'actor_role', None) != 'teacher'
            or type(target_seat_id) is not int or target_seat_id <= 0):
        raise ValueError('UNAUTHORIZED_SCOPE')


def get_historical_payroll_credit_records(*, ctx, class_id, target_seat_id, limit=1000):
    """Bound the complete target history before identity or compensation analysis."""
    _scope(ctx, class_id, target_seat_id)
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError('INVALID_INPUT')
    with db.session.no_autoflush:
        rows = Transaction.query.filter_by(class_id=class_id, seat_id=target_seat_id,
            target_seat_id=target_seat_id).order_by(Transaction.id.asc()).limit(limit+1).all()
    if len(rows)>limit:
        raise ValueError('EVIDENCE_LIMIT_EXCEEDED')
    return tuple(HistoricalLedgerRecord(tuple((field,getattr(row,field)) for field in _SOURCE_FIELDS))
        for row in rows)


def _replay(inputs, rule):
    if rule not in {'divide_first_half_even_28','multiply_first_half_even_28'}:
        return None
    if not inputs:
        return None
    policies = set()
    with localcontext() as context:
        context.prec = 28
        context.rounding = ROUND_HALF_EVEN
        total = Decimal(0)
        for share in inputs:
            if (not isinstance(share, HistoricalPricingInput)
                    or type(share.credited_seconds) is not int or share.credited_seconds < 0
                    or not isinstance(share.policy_locator,str) or not share.policy_locator
                    or not isinstance(share.rate_per_minute,str) or share.policy_locator in policies):
                return None
            policies.add(share.policy_locator)
            try:
                rate = Decimal(share.rate_per_minute)
                if not rate.is_finite() or rate < 0:
                    return None
                seconds = Decimal(share.credited_seconds)
                amount = seconds * (rate/Decimal(60)) if rule == 'divide_first_half_even_28' else seconds*rate/Decimal(60)
                total += amount.quantize(Decimal('.01'))
            except (InvalidOperation, ValueError, TypeError, OverflowError):
                return None
        return int(total*100)


def assess_historical_payroll_money(*, ctx, class_id, target_seat_id, business_input,
        records, audit_observations=(), creation_evidence=()):
    """Diagnostic comparison of explicitly supplied inputs, never proof adoption."""
    _scope(ctx,class_id,target_seat_id)
    if (not isinstance(business_input, HistoricalPayrollMoneyInput)
            or business_input.class_id != class_id or business_input.target_seat_id != target_seat_id
            or len(records)>1000
            or any(r.class_id!=class_id or r.seat_id!=target_seat_id or r.target_seat_id!=target_seat_id for r in records)):
        raise ValueError('UNAUTHORIZED_SCOPE')
    replay = _replay(business_input.pricing_inputs,business_input.arithmetic_rule)
    reasons = ['DIAGNOSTIC_DOES_NOT_AUTHORIZE_RECOVERY']
    candidates = [r for r in records if (
        (business_input.correlation_id and r.correlation_id==business_input.correlation_id)
        or (business_input.command_key and r.idempotency_key==business_input.command_key))]
    credit, cents = None, None
    identity = 'UNAVAILABLE'
    if len(candidates)==1:
        row = candidates[0]
        mechanism = str(getattr(row.mechanism,'value',row.mechanism)).lower()
        try:
            amount = Decimal(row.amount)
            if (amount.is_finite() and amount > 0 and amount == amount.quantize(Decimal('.01'))
                    and row.actor_seat_id==business_input.actor_seat_id
                    and mechanism==str(business_input.mechanism).lower()
                    and row.type==business_input.event_type and row.account_type=='checking'
                    and row.original_transaction_id is None):
                credit, cents, identity = row,int(amount*100),'UNIQUE_SCOPED_CANDIDATE'
        except (InvalidOperation, TypeError, ValueError):
            pass
    if credit is None:
        reasons.append('CREDIT_IDENTITY_UNAVAILABLE' if len(candidates)<=1 else 'AMBIGUOUS_CREDIT_IDENTITY')
    # A proven arithmetic zero is a business boundary observation, never a zero
    # original credit or evidence of zero compensation.
    comparison = 'MATCH' if credit is not None and replay==cents else 'MISMATCH' if credit is not None and replay is not None else 'UNAVAILABLE'
    if replay==0 and not candidates:
        comparison='ZERO_BOUNDARY_NO_CREDIT'
    if replay is None:
        reasons.append('ORIGINAL_ARITHMETIC_INPUTS_UNAVAILABLE')
    if credit is not None and not evidence_matches(credit,class_id,creation_evidence):
        reasons.append('CANONICAL_CREATION_PROOF_NOT_ASSESSED')
    # This diagnostic does not duplicate the canonical compensation proof.
    # Missing historical fields/signatures never imply no earlier recovery.
    recovered = None
    completeness = 'UNAVAILABLE'
    reasons.append('COMPENSATION_COMPLETENESS_UNAVAILABLE')
    return HistoricalMoneyAssessment(identity,ledger_origin_locator(credit) if credit else None,
        cents,replay,comparison,completeness,recovered,'BLOCKED_DIAGNOSTIC_ONLY',tuple(reasons))
