"""FEAT coordination of Operations creation evidence and Ledger proof inputs."""

from app.services.ledger_evidence import LedgerCreationEvidence
from app.services.ledger_recovery_service import (
    get_credit_recovery_evidence_records,
    ledger_origin_locator,
    lock_recovery_scope,
)
from app.services.class_configuration_query_service import get_banking_directive
from app.utils.audit_verifier import verified_creation_evidence


def positive_reversal_inputs(transaction):
    """Collect scoped, verified facts after taking the canonical monetary locks."""
    locator = ledger_origin_locator(transaction)
    lock_recovery_scope(transaction.class_id, transaction.seat_id, locator)
    evidence = []
    for row in get_credit_recovery_evidence_records(
        class_id=transaction.class_id,
        target_seat_id=transaction.seat_id,
        origin_locator=locator,
    ):
        verified = verified_creation_evidence(
            "ledger_transaction", row, transaction.class_id
        )
        if verified is None:
            raise ValueError("PROVENANCE_UNAVAILABLE")
        evidence.append(
            LedgerCreationEvidence(
                table_name=verified.table_name,
                row_pk=verified.row_pk,
                class_id=verified.class_id,
                lineage_event_id=verified.lineage_event_id,
                lineage_token=verified.lineage_token,
                signature_version=verified.signature_version,
                protected_fields=verified.protected_fields,
                field_values=verified.protected_values,
            )
        )
    return {
        "banking_directive": get_banking_directive(transaction.class_id),
        "creation_evidence": tuple(evidence),
    }
