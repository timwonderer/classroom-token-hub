"""Immutable Ledger proof inputs supplied by the originating FEAT.

Operations verifies records; FEAT maps its proof to this Ledger-owned shape.
Ledger performs no cross-domain query and accepts no request bypass switch.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LedgerCreationEvidence:
    table_name: str
    row_pk: str
    class_id: str
    lineage_event_id: int
    lineage_token: str
    signature_version: int
    protected_fields: tuple
    field_values: tuple


def evidence_matches(row, class_id, evidence, required_fields=()):
    proof = next(
        (
            item
            for item in evidence
            if isinstance(item, LedgerCreationEvidence)
            and item.table_name == "ledger_transaction"
            and item.row_pk == str(row.id)
            and item.class_id == class_id
        ),
        None,
    )
    if proof is None:
        return False
    if (
        proof.lineage_event_id != row.lineage_event_id
        or proof.lineage_token != row.lineage_token
        or proof.signature_version != row.lineage_version
    ):
        return False
    if not set(required_fields).issubset(proof.protected_fields):
        return False
    if {field for field, value in proof.field_values} != set(proof.protected_fields):
        return False
    return all(
        hasattr(row, field) and getattr(row, field) == value
        for field, value in proof.field_values
    )
