"""FEAT-PROD-006: pure historical assessment, no recovery or proof adoption."""
from dataclasses import dataclass
from app.extensions import db
from app.services.identity_service import resolve_teacher_target_seat
from app.services.class_configuration_query_service import verify_teacher_owns_class
from app.services.payroll.settings import get_historical_payroll_setting_inputs
from app.services.historical_attendance_assessment import (
    HistoricalAssessmentDenied, get_historical_attendance_business_evidence,
)
from app.services.ledger_historical_assessment import (
    HistoricalPricingInput, HistoricalPayrollMoneyInput,
    get_historical_payroll_credit_records, assess_historical_payroll_money,
)
from app.utils.canonical_temporal_resolver import CLASS_LEVEL_EVALUATION, canonical_temporal_resolver


@dataclass(frozen=True)
class HistoricalAttendanceAssessment:
    business: object
    money: tuple
    audit_coverage: tuple
    current_execution_eligibility: str = 'BLOCKED_DIAGNOSTIC_ONLY'


def assess_historical_attendance_proof(*, ctx, target_seat_id, payroll_event_ids=None, limit=50):
    """Authenticate current context before any target source or setting query."""
    if (type(target_seat_id) is not int or target_seat_id <= 0
            or type(limit) is not int or not 1<=limit<=100
            or (payroll_event_ids is not None and (not isinstance(payroll_event_ids,(tuple,list))
                or len(payroll_event_ids)>100 or any(type(i) is not int or i<=0 for i in payroll_event_ids)
                or len(set(payroll_event_ids))!=len(payroll_event_ids)))):
        raise HistoricalAssessmentDenied('INVALID_INPUT')
    with db.session.no_autoflush:
        try:
            resolve_teacher_target_seat(ctx=ctx,target_seat_id=target_seat_id)
            if verify_teacher_owns_class(ctx.class_id,ctx.user_id) is None:
                raise ValueError('UNAUTHORIZED_SCOPE')
        except (ValueError,AttributeError):
            raise HistoricalAssessmentDenied('UNAUTHORIZED_SCOPE') from None
        settings = get_historical_payroll_setting_inputs(ctx=ctx,class_id=ctx.class_id)
        at = canonical_temporal_resolver(CLASS_LEVEL_EVALUATION,
            canonical_execution_context=ctx,primitive='current_time').canonical_now_utc
        business = get_historical_attendance_business_evidence(ctx=ctx,class_id=ctx.class_id,
            target_seat_id=target_seat_id,setting_inputs=settings,payroll_event_ids=payroll_event_ids,
            limit=limit,as_of_utc=at)
        records = get_historical_payroll_credit_records(ctx=ctx,class_id=ctx.class_id,target_seat_id=target_seat_id)
        from app.utils.audit_verifier import diagnose_historical_audit_coverages
        diagnostics = diagnose_historical_audit_coverages('ledger_transaction',records,ctx.class_id)
        # Diagnostics never become canonical creation evidence. Existing
        # v2/v3 proof queries remain independent and unchanged.
        money=[]
        for event in business.events:
            inputs=HistoricalPayrollMoneyInput(ctx.class_id,target_seat_id,event.actor_seat_id,
                event.mechanism,event.event_type,event.correlation_id,event.command_key,
                event.rule.arithmetic_rule,tuple(HistoricalPricingInput(p.policy_locator,
                    p.credited_seconds,p.rate_per_minute) for p in event.pricing_inputs))
            money.append((event.event_id,assess_historical_payroll_money(ctx=ctx,class_id=ctx.class_id,
                target_seat_id=target_seat_id,business_input=inputs,records=records,
                audit_observations=diagnostics)))
        return HistoricalAttendanceAssessment(business,tuple(money),diagnostics)
