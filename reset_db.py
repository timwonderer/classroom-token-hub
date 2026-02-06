from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # Drop all tables
    db.drop_all()
    # Create all tables (this includes my new changes in models.py)
    db.create_all()

    # Manually insert alembic version if we want to pretend we are migrated?
    # No, if we want to generate a migration for the *difference* between the *migrations folder* and the *models*,
    # we need the database to be "stamped" with the latest migration that *successfully* runs.

    # But wait, if I want to generate a migration for MY changes, I need the migrations folder to match the DB *before* my changes.
    # But the migrations folder currently contains `9e7a8d4f5c6b`, which fails on SQLite.

    print("Database reset complete.")
