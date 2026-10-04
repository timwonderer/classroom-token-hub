"""Migration f4b8d2a6c1e9 converts users.id to a UUID without moving anyone.

Every fresh test database already runs the integer-to-UUID conversion: the
frozen baseline creates integer ids and the chain converts them. These tests
add what a fresh chain cannot, which is rows. They check that each principal
keeps its seats, classes and passkeys in both directions,
and that the conversion refuses a database whose references it doesn't
recognise.
"""

from __future__ import annotations

import pytest
from alembic import command
from flask import current_app
from flask_migrate import downgrade as alembic_downgrade
from flask_migrate import upgrade as alembic_upgrade
from sqlalchemy import text

from app.extensions import db
from tests.helpers.migration_schema import BEFORE_UUID_SOURCE, predecessor_classrooms

PREVIOUS = "e1c7a4b9d2f3"

LINKS = """
    SELECT 'seat', s.id::text, u.username_hash FROM seats s JOIN users u ON u.id = s.user_id
    UNION ALL SELECT 'class', c.class_id, u.username_hash FROM classes c JOIN users u ON u.id = c.teacher_user_id
    UNION ALL SELECT 'passkey', p.credential_id, u.username_hash FROM passkey_credentials p JOIN users u ON u.id = p.user_id
    ORDER BY 1, 2, 3
"""


def _rows(sql):
    with db.engine.connect() as conn:
        return conn.execute(text(sql)).all()


def _id_type():
    return _rows(
        "SELECT data_type FROM information_schema.columns"
        " WHERE table_schema = current_schema() AND table_name = 'users' AND column_name = 'id'"
    )[0][0]


def _seed(app):
    predecessor_classrooms(BEFORE_UUID_SOURCE, PREVIOUS,
                           ("chemistry_p1", "ap_csp_p3"), with_passkey=True)
    return _rows(LINKS)


def test_downgrade_and_upgrade_keep_every_principal_link(app):
    with app.app_context():
        before = _seed(app)
        assert _id_type() == "integer"
        alembic_upgrade(revision="f4b8d2a6c1e9")
        assert _id_type() == "uuid"
        assert _rows(LINKS) == before
        assert len(before) > 3

        alembic_downgrade(revision=PREVIOUS)
        assert _id_type() == "integer"
        assert _rows(LINKS) == before

        alembic_upgrade(revision="f4b8d2a6c1e9")
        assert _id_type() == "uuid"
        assert _rows(LINKS) == before


def test_conversion_refuses_a_reference_outside_the_allowlist(app):
    with app.app_context():
        predecessor_classrooms(BEFORE_UUID_SOURCE, PREVIOUS, ())
        with db.engine.begin() as conn:
            conn.execute(text("CREATE TABLE stray_ref (id serial PRIMARY KEY, user_id integer REFERENCES users(id))"))
        try:
            # Alembic directly: flask_migrate turns the exception into SystemExit.
            config = current_app.extensions["migrate"].migrate.get_config()
            with pytest.raises(RuntimeError, match="outside the INV-ARC-019"):
                command.upgrade(config, "f4b8d2a6c1e9")
        finally:
            db.session.remove()
            with db.engine.begin() as conn:
                conn.execute(text("DROP TABLE IF EXISTS stray_ref"))
        assert _id_type() == "integer"
        alembic_upgrade(revision="f4b8d2a6c1e9")
        assert _id_type() == "uuid"
