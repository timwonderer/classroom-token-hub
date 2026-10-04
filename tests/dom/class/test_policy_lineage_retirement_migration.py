"""Migrations dd52b19d48d8 and 624c6b7223df (operator ruling 2026-09-30).

dd52b19d48d8 retires ``policy_versions`` / ``policy_transitions`` and the
``assessment_events`` pointers into them. It drops the payroll mirror rows
(``payroll_settings`` is the payroll authority) and refuses, changing nothing,
when any row would carry meaning the owning tables do not hold: a non-payroll
version, any transition, or an assessment that names a version.

624c6b7223df gives ``economic_engine`` versions an effective date, set to
``created_at`` for every existing version, without leaving the table's
append-only trigger disabled, and fills it from ``created_at`` on an insert
that names none.

A fresh chain runs both over empty tables; these tests add the rows a fresh chain
cannot, shaped like production on 2026-09-30 (7 payroll ``policy_versions`` rows,
no transitions, no assessment naming a version).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from alembic import command
from flask import current_app
from flask_migrate import downgrade as alembic_downgrade
from flask_migrate import upgrade as alembic_upgrade
from sqlalchemy import text

from app.extensions import db
from tests.helpers.migration_schema import PAYROLL_AUTHORITY_SOURCE, predecessor_classrooms

BEFORE_RETIREMENT = "a7e3c9d1f5b2"
RETIREMENT = "dd52b19d48d8"
T0 = datetime(2026, 9, 28, 15, 0, tzinfo=timezone.utc)


def _rows(sql, **params):
    with db.engine.connect() as conn:
        return conn.execute(text(sql), params).all()


def _tables():
    return {
        name for (name,) in _rows(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()"
        )
    }


def _columns(table):
    return {
        name for (name,) in _rows(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_schema = current_schema() AND table_name = :t", t=table,
        )
    }


def _provision_predecessor(keys, revision=BEFORE_RETIREMENT):
    classrooms = predecessor_classrooms(PAYROLL_AUTHORITY_SOURCE, BEFORE_RETIREMENT, keys)
    if revision != BEFORE_RETIREMENT:
        alembic_upgrade(revision=revision)
    return [(c["class_id"], c["seat_id"]) for c in classrooms]


def _seed_payroll_mirrors(class_ids):
    with db.engine.begin() as conn:
        for cid in class_ids:
            conn.execute(text(
                "INSERT INTO policy_versions (policy_uuid, class_id, domain, version_number,"
                " policy_payload_json, created_at, activated_at, is_active)"
                " VALUES (:u, :c, 'payroll', 1, '{}', :t, :t, true)"
            ), {"u": str(uuid.uuid4()), "c": cid, "t": T0})


def _upgrade_expecting_refusal(match):
    config = current_app.extensions["migrate"].migrate.get_config()
    # Alembic directly: flask_migrate turns the exception into SystemExit.
    with pytest.raises(RuntimeError, match=match):
        command.upgrade(config, "head")
    db.session.remove()


def _assert_nothing_retired():
    assert {"policy_versions", "policy_transitions"} <= _tables()
    assert {"policy_version_id", "rent_policy_version_id"} <= _columns("assessment_events")


def test_upgrade_drops_the_payroll_mirrors_and_both_tables(app):
    with app.app_context():
        keys = ("tz_pacific_p1", "tz_line_islands_p1", "tz_tokyo_p1", "chemistry_p1",
                "ap_csp_p3", "biology_block_a", "unicode")
        ids = _provision_predecessor(keys)
        _seed_payroll_mirrors([cid for cid, _seat in ids])
        assert _rows("SELECT count(*) FROM policy_versions")[0][0] == 7

        alembic_upgrade()

        assert not ({"policy_versions", "policy_transitions"} & _tables())
        assert not ({"policy_version_id", "rent_policy_version_id"} & _columns("assessment_events"))


def test_upgrade_refuses_a_version_outside_payroll(app):
    with app.app_context():
        (cid, _seat), = _provision_predecessor(("chemistry_p1",))
        _seed_payroll_mirrors([cid])
        with db.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO policy_versions (policy_uuid, class_id, domain, version_number,"
                " policy_payload_json, created_at, is_active)"
                " VALUES (:u, :c, 'insurance', 1, '{\"premium\": \"5.00\"}', :t, true)"
            ), {"u": str(uuid.uuid4()), "c": cid, "t": T0})

        _upgrade_expecting_refusal("1 policy_versions row\\(s\\) in domain 'insurance'")
        _assert_nothing_retired()
        assert _rows("SELECT count(*) FROM policy_versions")[0][0] == 2

        with db.engine.begin() as conn:
            conn.execute(text("DELETE FROM policy_versions WHERE domain = 'insurance'"))
        alembic_upgrade()


def test_upgrade_refuses_any_transition(app):
    with app.app_context():
        (cid, _seat), = _provision_predecessor(("chemistry_p1",))
        _seed_payroll_mirrors([cid])
        with db.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO policy_transitions (class_id, domain, target_policy_version_id,"
                " activation_mode, status, created_at)"
                " SELECT class_id, 'rent', id, 'next_renewal', 'pending', :t FROM policy_versions"
            ), {"t": T0})

        _upgrade_expecting_refusal("1 policy_transitions row")
        _assert_nothing_retired()

        with db.engine.begin() as conn:
            conn.execute(text("DELETE FROM policy_transitions"))
        alembic_upgrade()


def test_upgrade_refuses_an_assessment_that_names_a_version(app):
    with app.app_context():
        (cid, seat_id), = _provision_predecessor(("chemistry_p1",))
        _seed_payroll_mirrors([cid])
        with db.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO assessment_events (seat_id, class_id, internal_ref, correlation_id,"
                " event_type, obligation_type, policy_version_id, \"timestamp\")"
                " SELECT :s, :c, 'rent:x', 'rent:x:1', 'ASSESSMENT', 'RENT', id, :t"
                " FROM policy_versions WHERE class_id = :c"
            ), {"s": seat_id, "c": cid, "t": T0})

        _upgrade_expecting_refusal("1 assessment_events row\\(s\\) with a policy_version_id")
        _assert_nothing_retired()

        with db.engine.begin() as conn:
            conn.execute(text("DELETE FROM assessment_events"))
        alembic_upgrade()


def test_downgrade_recreates_the_tables_empty_and_upgrade_retires_them_again(app):
    with app.app_context():
        (cid, _seat), = _provision_predecessor(("chemistry_p1",))
        _seed_payroll_mirrors([cid])
        alembic_upgrade(revision="624c6b7223df")

        alembic_downgrade(revision=BEFORE_RETIREMENT)
        _assert_nothing_retired()
        # The dropped rows are not restored.
        assert _rows("SELECT count(*) FROM policy_versions")[0][0] == 0
        assert _rows("SELECT count(*) FROM policy_transitions")[0][0] == 0

        alembic_upgrade(revision="624c6b7223df")
        assert not ({"policy_versions", "policy_transitions"} & _tables())


def test_engine_versions_are_dated_to_their_creation_and_stay_append_only(app):
    with app.app_context():
        ids = _provision_predecessor(("chemistry_p1", "ap_csp_p3"), revision=RETIREMENT)
        assert "effective_at" not in _columns("economic_engine")
        created = dict(_rows(
            "SELECT economic_version_id, created_at FROM economic_engine WHERE class_id = ANY(:c)",
            c=[cid for cid, _seat in ids],
        ))
        assert created

        alembic_upgrade()

        dated = dict(_rows(
            "SELECT economic_version_id, effective_at FROM economic_engine WHERE class_id = ANY(:c)",
            c=[cid for cid, _seat in ids],
        ))
        assert dated == created
        # The backfill re-enabled the append-only trigger.
        with pytest.raises(Exception, match="immutable"):
            with db.engine.begin() as conn:
                conn.execute(text("UPDATE economic_engine SET expected_weekly_hours = 1"))
        # A writer that names no effective_at records a version in force when saved.
        cid = ids[0][0]
        with db.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO economic_engine (economic_version_id, class_id, economy_policy_mode, created_at)"
                " VALUES (:v, :c, 'tight', :t)"
            ), {"v": str(uuid.uuid4()), "c": cid, "t": T0})
        assert _rows(
            "SELECT effective_at = created_at FROM economic_engine WHERE class_id = :c AND created_at = :t",
            c=cid, t=T0,
        ) == [(True,)]
