
import pytest
from app.models import Seat, Class
from app.extensions import db
from sqlalchemy.exc import IntegrityError

def test_class_scoping_enforcement(app):
    with app.app_context():
        # Ensure class_id is required
        seat = Seat(role="STUDENT", public_id="pub-1")
        db.session.add(seat)
        with pytest.raises(IntegrityError):
            db.session.commit()
