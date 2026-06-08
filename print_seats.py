from app import create_app, db
from app.models import Seat, Student, Admin
app = create_app()
with app.app_context():
    pass
