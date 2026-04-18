from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db
from app.services import ledger_service, obligations_service
from app.utils.time import utc_now
from app.utils.transaction_idempotency import insurance_reimbursement_key


@dataclass
class InsuranceClaimResolutionResult:
    claim_id: int
    reimbursement_transaction_id: int | None


def execute_insurance_claim_resolution(
    *,
    claim,
    enrollment,
    new_status: str,
    teacher_notes: str | None,
    rejection_reason: str | None,
    processed_by_teacher_id: int | None,
    approved_amount: Decimal | None,
):
    """Obligations-led FEAT for insurance claim resolution and reimbursement."""
    processed_at = utc_now()
    obligations_service.apply_claim_resolution(
        claim,
        status=new_status,
        teacher_notes=teacher_notes,
        rejection_reason=rejection_reason,
        processed_by_teacher_id=processed_by_teacher_id,
        processed_at=processed_at,
        approved_amount=approved_amount,
    )

    reimbursement_tx_id = None
    if approved_amount is not None and new_status in ("approved", "paid"):
        transaction_description = f"Insurance reimbursement for claim #{claim.id} ({enrollment.contract_title})"
        if claim.transaction_id:
            transaction_description += f" linked to transaction #{claim.transaction_id}"
        reimbursement_tx, _created = ledger_service.create_pending_transaction_idempotent(
            idempotency_key=insurance_reimbursement_key(claim.id),
            student_id=claim.student_id,
            teacher_id=processed_by_teacher_id,
            join_code=enrollment.join_code,
            amount=approved_amount,
            account_type="checking",
            type="insurance_reimbursement",
            description=transaction_description,
            original_transaction_id=claim.transaction_id,
            policy_id=claim.policy_id,
        )
        reimbursement_tx_id = reimbursement_tx.id

    db.session.commit()
    return InsuranceClaimResolutionResult(claim_id=claim.id, reimbursement_transaction_id=reimbursement_tx_id)
