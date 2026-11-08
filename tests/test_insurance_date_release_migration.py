"""Rehearse history-preserving date-lock constraint removal and safe rollback."""
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.extensions import db


def test_date_release_upgrade_downgrade_and_history_guard(app):
    path = Path(__file__).resolve().parents[1] / "migrations/versions/a91c3d7e5f20_insurance_rejected_date_release.py"
    spec = importlib.util.spec_from_file_location("date_release_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with app.app_context(), db.engine.connect() as connection:
        transaction = connection.begin()
        try:
            schema = f"rehearsal_{uuid4().hex}"
            connection.execute(sa.text(f"CREATE SCHEMA {schema}"))
            connection.execute(sa.text(f"SET LOCAL search_path TO {schema}"))
            connection.execute(sa.text("CREATE TABLE insurance_claim_productivity_dates (claim_id text, entitlement_id text, claim_date date, CONSTRAINT deployed_different_name UNIQUE (entitlement_id, claim_date), UNIQUE (claim_id, claim_date))"))
            connection.execute(sa.text("INSERT INTO insurance_claim_productivity_dates VALUES ('first','coverage','2026-11-02')"))
            migration.op = Operations(MigrationContext.configure(connection))
            migration.upgrade()
            migration.upgrade()
            migration.downgrade()
            migration.downgrade()
            migration.upgrade()
            connection.execute(sa.text("INSERT INTO insurance_claim_productivity_dates VALUES ('refiled','coverage','2026-11-02')"))
            with pytest.raises(RuntimeError, match="re-filed claim history"):
                migration.downgrade()
            assert connection.execute(sa.text("SELECT count(*) FROM insurance_claim_productivity_dates")).scalar() == 2
        finally:
            transaction.rollback()
