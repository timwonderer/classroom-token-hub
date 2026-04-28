
from app.extensions import db
from app.models import LedgerTransaction, LedgerBalanceSnapshot

def get_balance(seat_id):
    snapshot = db.session.get(LedgerBalanceSnapshot, seat_id)
    return snapshot.posted_balance_cents if snapshot else 0

def get_transactions(seat_id, limit=50):
    return LedgerTransaction.query.filter_by(seat_id=seat_id).order_by(LedgerTransaction.timestamp.desc()).limit(limit).all()
