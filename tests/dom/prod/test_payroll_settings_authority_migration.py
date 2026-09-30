"""Migration a7e3c9d1f5b2: payroll_settings becomes the effective-dated authority.

A fresh chain runs the migration over empty tables. These tests add what a
fresh chain cannot, which is rows shaped like production on 2026-09-29: seven
classes, one payroll_settings row and one payroll PolicyVersion each, payroll
events holding the PolicyVersion's id and uuid. They check the exact remap, the
refusal on data it would have to guess about, and a downgrade/upgrade cycle.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from alembic import command
from flask import current_app
from flask_migrate import downgrade as alembic_downgrade
from flask_migrate import upgrade as alembic_upgrade
from sqlalchemy import text

from app.extensions import db
from tests.helpers.canonical_classroom import provision_classroom

PREVIOUS = "f4b8d2a6c1e9"
THIS = "a7e3c9d1f5b2"
CLASSROOM_KEYS = (
    "tz_pacific_p1", "tz_line_islands_p1", "tz_tokyo_p1", "chemistry_p1",
    "ap_csp_p3", "biology_block_a", "unicode",
)
T0 = datetime(2026, 9, 28, 15, 0, tzinfo=timezone.utc)


def _rows(sql, **params):
    with db.engine.connect() as conn:
        return conn.execute(text(sql), params).all()


def _columns(table):
    return {
        name for (name,) in _rows(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_schema = current_schema() AND table_name = :t", t=table,
        )
    }


def _provision_and_downgrade(keys):
    """Plain ids of freshly provisioned classes, the schema stepped back one revision."""
    classrooms = []
    for key in keys:
        classroom = provision_classroom(key)
        classrooms.append(SimpleNamespace(
            class_id=classroom.class_id,
            seat_id=classroom.students[0].seat.id,
            teacher_seat_id=classroom.teacher_seat_id,
        ))
    db.session.commit()
    db.session.remove()
    alembic_downgrade(revision=PREVIOUS)
    return classrooms


def _seed_production_shape(classrooms, *, events_per_class=3):
    """Per class: one payroll PolicyVersion and payroll events that name it, plus
    a teacher manual credit that carries no provenance at all."""
    expected = {}
    with db.engine.begin() as conn:
        for index, classroom in enumerate(classrooms):
            cid = classroom.class_id
            pv_uuid = str(uuid.uuid4())
            pv_id = conn.execute(text(
                "INSERT INTO policy_versions (policy_uuid, class_id, domain, version_number,"
                " policy_payload_json, created_at, activated_at, is_active)"
                " VALUES (:u, :c, 'payroll', 1, '{}', :t, :t, true) RETURNING id"
            ), {"u": pv_uuid, "c": cid, "t": T0}).scalar()
            settings_uuid = conn.execute(text(
                "SELECT policy_uuid FROM payroll_settings WHERE class_id = :c"
            ), {"c": cid}).scalar()
            seat_id = classroom.seat_id
            for n in range(events_per_class):
                conn.execute(text(
                    "INSERT INTO payroll_event (class_id, target_seat_id, actor_seat_id, correlation_id,"
                    " idempotency_key, policy_version_id, policy_uuid, mechanism, payroll_event_type,"
                    " recorded_at, summary_json)"
                    " VALUES (:c, :s, :a, :corr, :k, :pv, :pvu, 'TEACHER', 'payroll', :t, '{}')"
                ), {
                    "c": cid, "s": seat_id, "a": classroom.teacher_seat_id,
                    "corr": f"corr-{index}-{n}", "k": f"key-{index}-{n}",
                    "pv": pv_id, "pvu": pv_uuid, "t": T0 + timedelta(hours=n + 1),
                })
            conn.execute(text(
                "INSERT INTO payroll_event (class_id, target_seat_id, actor_seat_id, correlation_id,"
                " idempotency_key, policy_version_id, policy_uuid, mechanism, payroll_event_type,"
                " recorded_at, summary_json)"
                " VALUES (:c, :s, :a, :corr, :k, NULL, NULL, 'TEACHER', 'manual_credit', :t, '{}')"
            ), {
                "c": cid, "s": seat_id, "a": classroom.teacher_seat_id,
                "corr": f"credit-{index}", "k": f"credit-{index}", "t": T0 + timedelta(hours=9),
            })
            expected[cid] = (settings_uuid, pv_uuid)
    return expected


def test_upgrade_remaps_every_event_to_its_classs_payroll_setting(app):
    with app.app_context():
        classrooms = _provision_and_downgrade(CLASSROOM_KEYS)
        expected = _seed_production_shape(classrooms)
        created = dict(_rows("SELECT class_id, created_at FROM payroll_settings"))

        alembic_upgrade()

        assert "policy_version_id" not in _columns("payroll_event")
        assert _columns("payroll_settings") == {
            "policy_uuid", "class_id", "pay_rate", "payroll_frequency_days", "effective_date",
            "created_at", "overtime_threshold", "overtime_threshold_unit", "max_time_per_day",
            "max_time_per_day_unit", "pay_schedule_type", "rounding_mode", "first_pay_date",
        }
        for cid, (settings_uuid, _pv_uuid) in expected.items():
            remapped = _rows(
                "SELECT DISTINCT policy_uuid FROM payroll_event"
                " WHERE class_id = :c AND payroll_event_type = 'payroll'", c=cid,
            )
            assert remapped == [(settings_uuid,)]
            assert _rows(
                "SELECT policy_uuid FROM payroll_event WHERE class_id = :c"
                " AND payroll_event_type = 'manual_credit'", c=cid,
            ) == [(None,)]
            assert _rows(
                "SELECT effective_date = created_at, created_at FROM payroll_settings WHERE class_id = :c", c=cid,
            ) == [(True, created[cid])]
        assert _rows("SELECT count(*) FROM payroll_event WHERE payroll_event_type = 'payroll'")[0][0] == 21
        # Append-only is live on the migrated rows.
        with pytest.raises(Exception, match="append-only"):
            with db.engine.begin() as conn:
                conn.execute(text("UPDATE payroll_settings SET pay_rate = 1"))


def test_upgrade_refuses_a_class_with_more_than_one_candidate_setting(app):
    with app.app_context():
        classrooms = _provision_and_downgrade(("chemistry_p1",))
        _seed_production_shape(classrooms, events_per_class=1)
        with db.engine.begin() as conn:
            # A second (retired) row for the class: which one priced the event?
            conn.execute(text(
                "INSERT INTO payroll_settings (policy_uuid, class_id, availability_state, pay_rate,"
                " payroll_frequency_days, created_at, updated_at, settings_mode, time_unit,"
                " overtime_enabled, pay_schedule_type, rounding_mode)"
                " VALUES (:u, :c, 'RETIRED', 0.1, 14, :t, :t, 'simple', 'minutes', false, 'biweekly', 'down')"
            ), {"u": str(uuid.uuid4()), "c": classrooms[0].class_id, "t": T0 - timedelta(days=1)})
        config = current_app.extensions["migrate"].migrate.get_config()
        # Alembic directly: flask_migrate turns the exception into SystemExit.
        with pytest.raises(RuntimeError, match="without exactly one payroll_settings row"):
            command.upgrade(config, "head")
        db.session.remove()
        # Nothing was changed: still the previous shape, still the PV reference.
        assert "policy_version_id" in _columns("payroll_event")
        assert "effective_date" not in _columns("payroll_settings")
        # Clear the ambiguity so the database can return to head for teardown.
        with db.engine.begin() as conn:
            conn.execute(text("DELETE FROM payroll_event"))
        alembic_upgrade()


def test_upgrade_refuses_an_event_whose_policy_version_is_another_classs(app):
    with app.app_context():
        classrooms = _provision_and_downgrade(("chemistry_p1", "ap_csp_p3"))
        _seed_production_shape(classrooms, events_per_class=1)
        with db.engine.begin() as conn:
            conn.execute(text(
                "UPDATE payroll_event SET policy_version_id = ("
                " SELECT id FROM policy_versions WHERE class_id = :other)"
                " WHERE class_id = :c AND payroll_event_type = 'payroll'"
            ), {"c": classrooms[0].class_id, "other": classrooms[1].class_id})
        config = current_app.extensions["migrate"].migrate.get_config()
        with pytest.raises(RuntimeError, match="outside their class"):
            command.upgrade(config, "head")
        db.session.remove()
        with db.engine.begin() as conn:
            conn.execute(text("DELETE FROM payroll_event"))
        alembic_upgrade()


def test_downgrade_and_upgrade_cycle_preserves_the_mapping(app):
    """Across this revision only. The next revision (dd52b19d48d8) retires
    policy_versions and recreates it empty on downgrade, so stepping back past
    both needs payroll PolicyVersions that no longer exist; that refusal is held
    in tests/dom/class/test_policy_lineage_retirement_migration.py."""
    with app.app_context():
        classrooms = _provision_and_downgrade(("chemistry_p1", "ap_csp_p3"))
        expected = _seed_production_shape(classrooms)
        alembic_upgrade(revision=THIS)

        alembic_downgrade(revision=PREVIOUS)
        assert "policy_version_id" in _columns("payroll_event")
        assert {"id", "availability_state", "next_payroll_date"} <= _columns("payroll_settings")
        for cid, (_settings_uuid, pv_uuid) in expected.items():
            # Restored to the PolicyVersion reference the old code expects.
            assert _rows(
                "SELECT DISTINCT e.policy_uuid, pv.policy_uuid FROM payroll_event e"
                " JOIN policy_versions pv ON pv.id = e.policy_version_id"
                " WHERE e.class_id = :c", c=cid,
            ) == [(pv_uuid, pv_uuid)]
            assert _rows(
                "SELECT availability_state FROM payroll_settings WHERE class_id = :c", c=cid,
            ) == [("IN_USE",)]

        alembic_upgrade()
        for cid, (settings_uuid, _pv_uuid) in expected.items():
            assert _rows(
                "SELECT DISTINCT policy_uuid FROM payroll_event"
                " WHERE class_id = :c AND payroll_event_type = 'payroll'", c=cid,
            ) == [(settings_uuid,)]


def test_retired_history_keeps_the_rate_that_was_in_force_at_each_instant(app):
    """A RETIRED row was in force from its creation until the next row superseded
    it, which is what effective_date := created_at answers. (No event names
    these rows, so there is nothing to remap and nothing to refuse.)"""
    from app.services.payroll.settings import payroll_setting_effective_at

    with app.app_context():
        (classroom,) = _provision_and_downgrade(("chemistry_p1",))
        cid = classroom.class_id
        older, newer = str(uuid.uuid4()), str(uuid.uuid4())
        with db.engine.begin() as conn:
            conn.execute(text("DELETE FROM payroll_settings WHERE class_id = :c"), {"c": cid})
            for policy_uuid, state, rate, created in (
                (older, "RETIRED", "0.10", T0), (newer, "IN_USE", "0.20", T0 + timedelta(days=2)),
            ):
                conn.execute(text(
                    "INSERT INTO payroll_settings (policy_uuid, class_id, availability_state, pay_rate,"
                    " payroll_frequency_days, created_at, updated_at, settings_mode, time_unit,"
                    " overtime_enabled, pay_schedule_type, rounding_mode)"
                    " VALUES (:u, :c, :s, :r, 14, :t, :t, 'advanced', 'minutes', false, 'biweekly', 'down')"
                ), {"u": policy_uuid, "c": cid, "s": state, "r": rate, "t": created})

        alembic_upgrade()

        assert payroll_setting_effective_at(cid, T0 + timedelta(days=1)).policy_uuid == older
        assert payroll_setting_effective_at(cid, T0 + timedelta(days=2)).policy_uuid == newer
        assert payroll_setting_effective_at(cid, T0 - timedelta(seconds=1)) is None
