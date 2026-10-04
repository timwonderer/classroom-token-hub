"""FEAT coordination of Operations creation evidence and Ledger proof inputs."""

from app.services.ledger_evidence import LedgerCreationEvidence
from app.services.ledger_recovery_service import (
    get_credit_recovery_evidence_records,
    ledger_origin_locator,
    lock_recovery_scope,
)
from app.services.class_configuration_query_service import get_banking_directive
from app.utils.audit_verifier import verified_creation_evidences


def to_ledger_creation_evidence(proof):
    """Map one Operations ``VerifiedCreationEvidence`` to the Ledger proof input."""
    return LedgerCreationEvidence(
        proof.table_name,
        proof.row_pk,
        proof.class_id,
        proof.lineage_event_id,
        proof.lineage_token,
        proof.signature_version,
        proof.protected_fields,
        proof.protected_values,
    )


def positive_reversal_inputs(transaction):
    """Collect scoped, verified facts after taking the canonical monetary locks."""
    locator = ledger_origin_locator(transaction)
    lock_recovery_scope(transaction.class_id, transaction.seat_id, locator)
    records = get_credit_recovery_evidence_records(
        class_id=transaction.class_id,
        target_seat_id=transaction.seat_id,
        origin_locator=locator,
    )
    # One bounded class-chain walk for every record (DOM-OPS-002 §6.2C).
    batch = verified_creation_evidences(
        [("ledger_transaction", row) for row in records], transaction.class_id
    )
    if any(proof is None for proof in batch.evidence):
        raise ValueError("PROVENANCE_UNAVAILABLE")
    return {
        "banking_directive": get_banking_directive(transaction.class_id),
        "creation_evidence": tuple(to_ledger_creation_evidence(proof) for proof in batch.evidence),
    }
