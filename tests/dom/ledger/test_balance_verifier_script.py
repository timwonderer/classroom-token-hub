"""The operator verifier uses derived posting and remains read-only."""
import runpy
from pathlib import Path

import app as app_module
from app.extensions import db
from app.models import Transaction, TransactionStatus
from tests.dom.prod.test_attendance_invalidation_command import _paid_sources


def test_balance_verifier_reads_reconciled_posting_without_mutation(app, monkeypatch, capsys):
    _paid_sources(app)
    expected = Transaction.query.filter(Transaction.posting_state == TransactionStatus.POSTED).count()
    before = [(t.id, t.amount_cents, t.posting_sequence, t.lineage_token)
              for t in Transaction.query.order_by(Transaction.id)]
    monkeypatch.setattr(app_module, 'create_app', lambda: app)
    runpy.run_path(str(Path(__file__).resolve().parents[3] / 'scripts/verify_balance_cache.py'), run_name='__main__')
    output = capsys.readouterr().out
    assert f'Posted Transactions: {expected}' in output
    assert f'Status={TransactionStatus.POSTED.value}' in output
    assert before == [(t.id, t.amount_cents, t.posting_sequence, t.lineage_token)
                      for t in Transaction.query.order_by(Transaction.id)]
