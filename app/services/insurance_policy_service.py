"""Canonical insurance-type taxonomy.

Insurance definitions live in ``insurance_policies`` (``insurance_definition_service``),
keyed by ``policy_uuid`` (DOM-POL-001 §VI.0). This module keeps only the type
taxonomy that the definition boundary and the Economic Engine share.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Canonical insurance-type taxonomy (owned here, at the insurance-definition
# boundary — NOT by the Economic Engine).
#
# Insurance type is a *definition* fact: it is assigned to a policy at
# definition time (FEAT-STOR-003 places the insurance definition and its type
# under Class Configuration). The Economic Engine merely *consumes* this type to
# select premium/coverage recommendations; it is not the authority for what an
# insurance type means. Keeping the taxonomy here prevents economic_engine.py
# from silently accreting definition semantics and becoming a god-service.
#
# The three canonical types are defined by SPEC-ECON-003 §4.5.
# ---------------------------------------------------------------------------
TRANSACTION = "TRANSACTION"
PRODUCTIVITY = "PRODUCTIVITY"
NON_MONETARY = "NON_MONETARY"
INSURANCE_TYPES = (TRANSACTION, PRODUCTIVITY, NON_MONETARY)

# Legacy claim_type taxonomy → canonical mapping. Single runtime source of truth
# for coercing pre-cutover payloads on read and at definition write time.
# Per SPEC-ECON-003 §4.5 and ARC-OPS-001:
#   - ``transaction_monetary`` was single-transaction reimbursement → TRANSACTION
#   - ``non_monetary``         was the external-benefit product       → NON_MONETARY
#   - ``legacy_monetary`` ("Variable Monetary") had NO defined reimbursement
#     architecture and is NOT lost-wage/attendance insurance. It is RETIRED —
#     collapsed into the generic TRANSACTION product, never reinterpreted as
#     PRODUCTIVITY (which has no historical data and is genuinely new behavior).
_LEGACY_INSURANCE_TYPE_ALIASES: dict[str, str] = {
    "transaction_monetary": TRANSACTION,
    "legacy_monetary": TRANSACTION,
    "non_monetary": NON_MONETARY,
    # Idempotent identity mappings so normalization is safe to re-run.
    "TRANSACTION": TRANSACTION,
    "PRODUCTIVITY": PRODUCTIVITY,
    "NON_MONETARY": NON_MONETARY,
}


def normalize_insurance_type(value: object) -> str:
    """Coerce any legacy or canonical insurance-type token to the canonical taxonomy.

    Unknown / missing values default to ``TRANSACTION`` (the generic monetary
    product) rather than inventing a PRODUCTIVITY reinterpretation.
    """
    if isinstance(value, str):
        return _LEGACY_INSURANCE_TYPE_ALIASES.get(value.strip(), TRANSACTION)
    return TRANSACTION
