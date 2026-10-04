"""SOP-DB-001 idempotency must preserve evidence and installed guards."""
from importlib import import_module

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import DBAPIError

from app.extensions import db
from app.models import AuditEvent, Transaction
from tests.dom.prod.test_attendance_invalidation_command import _paid_sources


REVISIONS = (
    'd6b1e0c4a825_payroll_creation_audit_lineage',
    'e7c2a9d4f610_derive_ledger_posting_from_reconciliation',
    'f8b2d6e0a410_ledger_compensation_provenance',
    'f9a3c7d1e620_attendance_interval_invalidation',
)


def test_repeated_upgrades_preserve_signed_rows_and_compensation_guards(app):
    _paid_sources(app)
    rows = [(t.id, t.amount_cents, t.posting_sequence, t.lineage_token)
            for t in Transaction.query.order_by(Transaction.id)]
    audits = [(a.id, a.payload_digest, a.event_hash, a.hmac_signature)
              for a in AuditEvent.query.order_by(AuditEvent.id)]
    original_id = next(t.id for t in Transaction.query.all() if t.amount_cents > 0)
    db.session.rollback()
    # Replaying the pre-v3 guard installer must not erase later protected
    # fields. Probe it before f8 can reinstall its own guard and mask a defect.
    with db.engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            import_module('migrations.versions.' + REVISIONS[1]).upgrade()
    for field, value in (
        ('compensation_origin_locator', 'ledger-credit:v1:999'),
        ('compensation_amount_cents', 1),
        ('correction_intent_locator', 'test:replaced-intent'),
    ):
        with pytest.raises(DBAPIError, match='Immutable Ledger field: ' + field):
            with db.engine.begin() as connection:
                connection.execute(
                    sa.text(f'UPDATE ledger_transaction SET {field}=:value WHERE id=:id'),
                    {'id': original_id, 'value': value},
                )
    with db.engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            for _ in range(2):
                for revision in REVISIONS:
                    import_module('migrations.versions.' + revision).upgrade()
        assert 'status' not in {c['name'] for c in sa.inspect(connection).get_columns('ledger_transaction')}
    assert rows == [(t.id, t.amount_cents, t.posting_sequence, t.lineage_token)
                    for t in Transaction.query.order_by(Transaction.id)]
    assert audits == [(a.id, a.payload_digest, a.event_hash, a.hmac_signature)
                      for a in AuditEvent.query.order_by(AuditEvent.id)]
    db.session.rollback()
    with pytest.raises(DBAPIError, match='Immutable Ledger field: compensation_amount_cents'):
        with db.engine.begin() as connection:
            connection.execute(sa.text('UPDATE ledger_transaction SET compensation_amount_cents=1 WHERE id=:id'),
                               {'id': original_id})
