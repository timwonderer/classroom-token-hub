from app import create_app, db
from sqlalchemy import inspect
import sys

app = create_app()
with app.app_context():
    insp = inspect(db.engine)
    if len(sys.argv) > 1:
        table_name = sys.argv[1]
    else:
        table_names = insp.get_table_names()
        table_name = table_names[0] if table_names else None

    if table_name is not None:
        cols = insp.get_columns(table_name)
    else:
        cols = []

    print(f"Columns found: {[c['name'] for c in cols]}")
    for c in cols:
        if c['name'] == 'created_at':
            print(f"Column created_at type: {c['type']}")
    sys.stdout.flush()
