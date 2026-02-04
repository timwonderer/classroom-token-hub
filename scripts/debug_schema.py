from app import create_app, db
from sqlalchemy import inspect

app = create_app()
with app.app_context():
    insp = inspect(db.engine)
    print(f"Columns found: {[c['name'] for c in cols]}")
    for c in cols:
        if c['name'] == 'created_at':
            print(f"Column created_at type: {c['type']}")
    import sys
    sys.stdout.flush()
