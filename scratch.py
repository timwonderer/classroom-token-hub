from app.extensions import db
from app import create_app
from app.models import Transaction, TransactionStatus
from app.feats.base import FEATBypass

app = create_app()
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
with app.app_context():
    db.create_all()
    tx = Transaction(
        amount=10.0,
        account_type='checking',
        status=TransactionStatus.POSTED,
        correlation_id='bypass_test_1'
    )
    db.session.add(tx)
    with FEATBypass():
        try:
            db.session.commit()
            print("SUCCESS")
            
            # verify seat_id
            print("seat_id is:", tx.seat_id)
        except Exception as e:
            print("FAILED:", e)
