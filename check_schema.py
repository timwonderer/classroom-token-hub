from app import create_app, db
from sqlalchemy import inspect

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    columns = inspector.get_columns('rent_items')
    print("Columns in rent_items:", [c['name'] for c in columns])
