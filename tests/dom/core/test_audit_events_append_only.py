"""INV-ARC-016 §VIII enforcement at the database boundary.

"`UPDATE` and `DELETE` on `audit_events` are prohibited in all environments."

The hash chain (`previous_hash` / `event_hash` / `hmac_signature` plus
`chain_heads`) makes tampering detectable. These tests assert the stronger
property the invariant actually states: that it is refused outright, by the
database, regardless of what the calling code believes it is allowed to do.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import InternalError, ProgrammingError

from app import db
from app.services.audit_service import emit_audit_event, system_audit_authority


@pytest.fixture
def audit_row(app):
    """One committed audit event to attack."""
    with system_audit_authority("test fixture: seed a row for immutability checks"):
        event = emit_audit_event(
            table_name="ledger_transaction",
            row_pk="1",
            operation="INSERT",
            protected_fields={"amount": "1.00"},
        )
    db.session.commit()
    return event.id


def test_INV_ARC_016__audit_events_cannot_be_updated(app, audit_row):
    with pytest.raises((InternalError, ProgrammingError), match="append-only"):
        db.session.execute(
            text("UPDATE audit_events SET payload_digest = 'tampered' WHERE id = :id"),
            {"id": audit_row},
        )
    db.session.rollback()


def test_INV_ARC_016__audit_events_cannot_be_deleted(app, audit_row):
    with pytest.raises((InternalError, ProgrammingError), match="append-only"):
        db.session.execute(
            text("DELETE FROM audit_events WHERE id = :id"),
            {"id": audit_row},
        )
    db.session.rollback()


def test_INV_ARC_016__universe_destruction_flag_does_not_exempt_audit_events(app, audit_row):
    """The class-destruction escape hatch stops at the audit chain.

    `prevent_immutable_delete()` yields to `cth.class_universe_destroying` so a
    destroyed class can shed its economic history. §VIII admits no exemption, so
    audit_events is bound to its own function that honours no flag.
    """
    db.session.execute(text("SET LOCAL cth.class_universe_destroying = 'on'"))
    with pytest.raises((InternalError, ProgrammingError), match="append-only"):
        db.session.execute(
            text("DELETE FROM audit_events WHERE id = :id"),
            {"id": audit_row},
        )
    db.session.rollback()


def test_INV_ARC_016__inserts_still_append(app, audit_row):
    """The guard must not freeze the chain it exists to protect."""
    with system_audit_authority("test: appending after the guard is installed"):
        second = emit_audit_event(
            table_name="ledger_transaction",
            row_pk="2",
            operation="INSERT",
            protected_fields={"amount": "2.00"},
        )
    db.session.commit()

    assert second.id != audit_row
    assert second.previous_hash is not None
