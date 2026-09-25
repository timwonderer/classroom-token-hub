"""Insurance premium-lineage provisioning for tests (SPEC-TEST-001 domain helper).

An insurance entitlement is usable only inside a coverage period of its premium
lineage and only while every premium due so far is paid (DOM-STORE-001
§VIII.E.1). Tests that hand-insert a GRANTED insurance event (to control its
policy or timestamp) use :func:`establish_paid_premium_lineage` to give it the
lineage a real purchase would have: cycle 1 from the grant, every later period
through ``through_utc``, each premium assessed and paid through the canonical
Obligations and Ledger commands — never hand-written rows.

Call inside a FEAT context (the test's setup scaffold).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from app.feats.assess_obligation_feat import AssessmentRequest, assess_obligation
from app.feats.insurance_premium_payment_feat import settle_insurance_premium
from app.feats.schedule_next_bill_cycle_feat import (
    ScheduleNextBillCycleRequest,
    schedule_next_bill_cycle,
)
from app.services.insurance_coverage_service import (
    class_local_date,
    coverage_boundary,
    premium_lineage_ref,
)
from app.services.insurance_definition_service import get_insurance_definition
from app.utils.canonical_temporal_resolver import ensure_utc, utc_now
from tests.helpers.ledger import create_ledger_idempotent_transaction


def establish_paid_premium_lineage(
    *,
    class_id: str,
    seat_id: int,
    entitlement_id: str,
    policy_uuid: str,
    start_utc: datetime,
    through_utc: datetime | None = None,
    paid: bool = True,
) -> list:
    """Create the entitlement's premium lineage from ``start_utc`` through ``through_utc``.

    Returns the bill cycles created. With ``paid`` each premium is funded and
    paid in full (net-zero on the seat's balance).
    """
    policy = get_insurance_definition(policy_uuid, class_id=class_id)
    premium = Decimal(str(policy.premium))
    start = ensure_utc(start_utc)
    through = ensure_utc(through_utc) if through_utc is not None else utc_now()
    anchor = class_local_date(class_id, start)
    lineage = premium_lineage_ref(entitlement_id)

    cycles = []
    cycle_start = start
    n = 1
    while True:
        cycle_end = coverage_boundary(
            class_id, anchor_date=anchor, charge_frequency=policy.charge_frequency, index=n
        )
        cycle = schedule_next_bill_cycle(
            ScheduleNextBillCycleRequest(
                class_id=class_id,
                internal_ref=lineage,
                cycle_boundary_at=cycle_start,
                next_assessment_at=cycle_end,
                idempotency_key=f"test-lineage:{entitlement_id}:cycle:{n}",
                policy_uuid=policy_uuid,
                reference_time_utc=cycle_start,
            ),
            context=None,
        )
        correlation_id = f"insurance-premium:{entitlement_id}:{n}"
        assess_obligation(
            AssessmentRequest(
                seat_id=seat_id, class_id=class_id, internal_ref=lineage,
                correlation_id=correlation_id, obligation_type="INSURANCE_PREMIUM",
                policy_uuid=policy_uuid, bill_cycle_id=cycle.id,
            ),
            context=None,
        )
        if paid and premium > Decimal("0.00"):
            create_ledger_idempotent_transaction(
                idempotency_key=f"test-lineage-fund:{entitlement_id}:{n}:{uuid4().hex}",
                seat_id=seat_id, class_id=class_id, amount=premium,
                account_type="checking", type="payroll",
                description="Test funding for an insurance premium",
            )
            settle_insurance_premium(
                class_id=class_id, seat_id=seat_id, correlation_id=correlation_id,
                amount=premium,
                ledger_idempotency_key=f"test-lineage-pay:{entitlement_id}:{n}",
                description=f"Test insurance premium (cycle {n})",
            )
        cycles.append(cycle)
        if cycle_end > through:
            return cycles
        cycle_start = cycle_end
        n += 1
