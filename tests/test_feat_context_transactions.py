from app import app, db
from app.feats.base import FEATContext
from sqlalchemy import text


def test_feat_context_allows_existing_session_transaction():
    """Top-level FEAT entry should not crash when a transaction is already active."""
    with app.app_context():
        with db.session.begin():
            with FEATContext("FEAT-IDEN-001"):
                db.session.execute(text("SELECT 1"))
