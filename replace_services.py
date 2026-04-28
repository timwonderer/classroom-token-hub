print("Realignment: Rewriting Services")
import os
os.system("rm -rf app/services/*")
os.makedirs("app/services", exist_ok=True)
with open("app/services/__init__.py", "w") as f:
    f.write("")

with open("app/services/ledger_service.py", "w") as f:
    f.write("""
from app.extensions import db
from app.models import LedgerTransaction, LedgerBalanceSnapshot

def get_balance(seat_id):
    snapshot = db.session.get(LedgerBalanceSnapshot, seat_id)
    return snapshot.posted_balance_cents if snapshot else 0

def get_transactions(seat_id, limit=50):
    return LedgerTransaction.query.filter_by(seat_id=seat_id).order_by(LedgerTransaction.timestamp.desc()).limit(limit).all()
""")

with open("app/services/store_service.py", "w") as f:
    f.write("""
from app.extensions import db
from app.models import StoreItem, StoreItemVisibility, StorePurchase

def get_catalog(class_id, seat_id=None):
    query = StoreItem.query.filter_by(class_id=class_id)
    if seat_id:
        query = query.join(StoreItemVisibility).filter(StoreItemVisibility.seat_id == seat_id)
    return query.all()
""")
