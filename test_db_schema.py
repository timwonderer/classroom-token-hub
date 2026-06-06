import pytest
from app import create_app, db
import sqlalchemy

app = create_app()
with app.app_context():
    print(app.config['SQLALCHEMY_DATABASE_URI'])
    with db.engine.connect() as conn:
        res = conn.execute(sqlalchemy.text("SELECT column_name FROM information_schema.columns WHERE table_name = 'hall_pass_settings'"))
        print([r[0] for r in res])
