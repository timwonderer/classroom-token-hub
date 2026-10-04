"""Schema fixtures using DOM-OPS-002 §6.1's frozen creation protocol.

These fixtures test immutable business-source queries and lifecycle guards, not
payroll pricing. Runtime pricing/recovery tests must use the registered FEAT.
No helper creates or alters monetary effects or claims historical attestation.
"""
from app.extensions import db
from app.feats.base import audit_protected, get_active_feat_name
from app.models import PayrollEvent
from app.utils.audit_verifier import PROTECTED_FIELDS_BY_TABLE


def record_payroll_source_fixture(**business_fields):
    """Freeze the source before INSERT, initialize real audit lineage once."""
    if get_active_feat_name() not in {"FEAT-PROD-003", "FEAT-PROD-004"}:
        raise ValueError("Payroll source fixtures require the governing PROD FEAT context.")
    row = PayrollEvent(**business_fields)
    db.session.add(row)
    db.session.flush()
    audit_protected("payroll_event", row, "INSERT", PROTECTED_FIELDS_BY_TABLE["payroll_event"])
    db.session.flush()
    return row
