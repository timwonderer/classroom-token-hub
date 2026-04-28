
from app.extensions import db
from app.models import StoreItem, StoreItemVisibility, StorePurchase

def get_catalog(class_id, seat_id=None):
    query = StoreItem.query.filter_by(class_id=class_id)
    if seat_id:
        query = query.join(StoreItemVisibility).filter(StoreItemVisibility.seat_id == seat_id)
    return query.all()
