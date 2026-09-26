"""Roster deletion is attributed to the FEAT that owns what it destroys.

``/admin/student/delete`` and ``/admin/students/bulk-delete`` reach three
different terminal scopes depending on what is left on the roster afterwards:

* removing some seats leaves the class and the principal standing;
* removing the last seats destroys the class universe, including the
  administrative Seat (DOM-CLASS-001 §Terminal Roster Deletion);
* doing that to the teacher's final class destroys the principal too, because a
  ``users`` row holding no Seat anywhere is an invariant violation
  (DOM-IDEN-005 §V.6 and §VI).

All three ran under ``FEAT-IDEN-006`` — "Provision Student Seat in Existing
Class", blast radius MED. Destruction still happened atomically and still
happened correctly; what was wrong was the attribution. ``feat_code`` on audit
and ledger rows, and every FEAT-ENTRY record, take their value from
``get_active_feat_name()`` (``app/models.py``, ``app/services/audit_service.py``),
so the most destructive operation in the system was recorded under a MED
provisioning FEAT, and the HIGH blast-radius idempotency discipline that
``FEAT-IDEN-007`` and ``FEAT-CLASS-006`` carry never applied to it.

Routing happens before the FEAT opens, from a preview that holds no lock, so the
selected executor re-derives the plan under lock and refuses when the terminal
scope has moved underneath it. These tests hold both halves: the right FEAT owns
each command, and a stale preview cannot borrow a narrow FEAT to perform a wider
destruction.
"""

from __future__ import annotations

import pytest

from app import db
from app.feats.base import FEAT_REGISTRY, get_active_feat_name
from app.models import ClassEconomy, Seat, User
from tests.dom.identity.helpers import valid_destruction_gate
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


def _bulk_delete(client, seat_ids, phrase):
    return client.post(
        "/admin/students/bulk-delete",
        json={"student_ids": list(seat_ids), **valid_destruction_gate(phrase)},
    )


def _student_seat_ids(class_id):
    return [seat.id for seat in Seat.query.filter_by(class_id=class_id, role="student").all()]


@pytest.fixture
def captured_feats(monkeypatch):
    """Record the FEAT active while each destructive command runs.

    The real command is still executed, so these tests assert the attribution
    and the resulting state together. ``get_active_feat_name()`` is the same
    accessor the audit and ledger listeners stamp into ``feat_code``.
    """
    import app.routes.admin as admin_module
    import app.utils.student_deletion as student_deletion_module

    seen: dict[str, list[str | None]] = {"seat": [], "class": [], "account": []}

    def recorder(label, module, name):
        original = getattr(module, name)

        def wrapper(*args, **kwargs):
            seen[label].append(get_active_feat_name())
            return original(*args, **kwargs)

        monkeypatch.setattr(module, name, wrapper)

    recorder("seat", student_deletion_module, "remove_student_from_teacher_scope")
    recorder("class", admin_module, "_destroy_class_scope_rows")
    recorder("account", admin_module, "_destroy_teacher_account_rows")
    return seen


def test_removing_some_seats_runs_under_the_student_seat_feat(client, app, captured_feats):
    """Seats go, the class and the principal stay: FEAT-IDEN-006 owns that."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    all_seats = _student_seat_ids(classroom.class_id)
    targets = all_seats[:2]

    response = _bulk_delete(client, targets, "DELETE STUDENTS")
    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_json()
    assert body["class_deleted"] is False and body["account_deleted"] is False

    assert captured_feats["seat"] == ["FEAT-IDEN-006", "FEAT-IDEN-006"]
    assert captured_feats["class"] == [] and captured_feats["account"] == []

    db.session.expire_all()
    assert sorted(_student_seat_ids(classroom.class_id)) == sorted(all_seats[2:])
    assert db.session.get(ClassEconomy, classroom.class_id) is not None
    assert db.session.get(User, classroom.teacher_user.id) is not None


def test_emptying_the_roster_runs_under_the_class_destruction_feat(client, app, captured_feats):
    """The class universe is destroyed, so FEAT-CLASS-006 owns the command."""
    surviving = initialize("ap_csp_p3", app)
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    teacher_user_id = classroom.teacher_user.id
    assert surviving.teacher_user.id == teacher_user_id

    response = _bulk_delete(client, _student_seat_ids(classroom.class_id), "DELETE CLASS")
    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_json()
    assert body["class_deleted"] is True and body["account_deleted"] is False

    assert captured_feats["class"] == ["FEAT-CLASS-006"]
    assert captured_feats["account"] == []
    # The narrow per-seat command must not also run: destroying the class
    # universe is one command, not a class teardown plus four seat removals.
    assert captured_feats["seat"] == []

    db.session.expire_all()
    assert db.session.get(ClassEconomy, classroom.class_id) is None
    assert db.session.get(User, teacher_user_id) is not None
    assert Seat.query.filter_by(user_id=teacher_user_id, class_id=surviving.class_id).count() == 1


def test_emptying_the_only_class_runs_under_teacher_account_destruction(client, app, captured_feats):
    """The principal cannot survive its final Seat: FEAT-IDEN-007 owns that."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    teacher_user_id = classroom.teacher_user.id

    response = _bulk_delete(client, _student_seat_ids(classroom.class_id), "DELETE TEACHER ACCOUNT")
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()["account_deleted"] is True

    assert captured_feats["account"] == ["FEAT-IDEN-007"]
    assert captured_feats["seat"] == []

    db.session.expire_all()
    assert db.session.get(User, teacher_user_id) is None
    assert db.session.get(ClassEconomy, classroom.class_id) is None


def test_the_recorded_feat_carries_the_blast_radius_of_the_destruction(client, app, captured_feats):
    """Audit lineage must name a HIGH FEAT, not the MED provisioning one.

    This is the finding itself: the attribution a destroyed account is recorded
    under. ``FEAT-IDEN-006`` is MED and is not permitted to be the answer.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)

    response = _bulk_delete(client, _student_seat_ids(classroom.class_id), "DELETE TEACHER ACCOUNT")
    assert response.status_code == 200, response.get_data(as_text=True)

    recorded = captured_feats["account"][0]
    assert recorded == "FEAT-IDEN-007"
    assert FEAT_REGISTRY[recorded]["blast_radius"] == "HIGH"
    assert recorded != "FEAT-IDEN-006"
    assert FEAT_REGISTRY["FEAT-IDEN-006"]["blast_radius"] == "MED"


def test_a_stale_preview_cannot_destroy_a_wider_scope_than_its_feat(client, app, captured_feats, monkeypatch):
    """The preview picks the FEAT; the locked plan decides, or nothing happens.

    The preview runs before any row is locked, so a concurrent claim, provision,
    or delete can move the terminal scope between choosing a FEAT and executing
    under it. Here the preview reports the narrow seats scope while the roster
    is in fact about to be emptied — the shape that would let FEAT-IDEN-006
    destroy a class and a principal. It must refuse instead.
    """
    import app.routes.admin as admin_module

    classroom = initialize_as_teacher("chemistry_p1", client, app)
    teacher_user_id = classroom.teacher_user.id
    seat_ids = _student_seat_ids(classroom.class_id)

    real_plan = admin_module._student_deletion_plan
    calls = {"n": 0}

    def narrowed_preview(context, ids):
        plan = real_plan(context, ids)
        calls["n"] += 1
        if calls["n"] == 1:
            # First call is the unlocked preview that selects the FEAT.
            return {**plan, "class_deleted": False, "account_deleted": False,
                    "expected_phrase": "DELETE STUDENTS"}
        return plan

    monkeypatch.setattr(admin_module, "_student_deletion_plan", narrowed_preview)

    response = _bulk_delete(client, seat_ids, "DELETE STUDENTS")
    assert response.status_code == 409, response.get_data(as_text=True)
    assert "nothing was deleted" in response.get_json()["message"].lower()

    # No destructive command of any scope ran.
    assert captured_feats == {"seat": [], "class": [], "account": []}

    db.session.expire_all()
    assert sorted(_student_seat_ids(classroom.class_id)) == sorted(seat_ids)
    assert db.session.get(ClassEconomy, classroom.class_id) is not None
    assert db.session.get(User, teacher_user_id) is not None


def test_a_failure_part_way_through_leaves_the_whole_roster_intact(client, app, monkeypatch):
    """The FEAT is still the transaction boundary after the restructure.

    Routing by scope moved which FEAT opens, not when it commits. A command that
    fails after deleting one seat must leave every seat in place.
    """
    import app.utils.student_deletion as student_deletion_module

    classroom = initialize_as_teacher("chemistry_p1", client, app)
    seat_ids = _student_seat_ids(classroom.class_id)
    targets = seat_ids[:2]

    original = student_deletion_module.remove_student_from_teacher_scope
    calls = {"n": 0}

    def fail_on_the_second(seat_id, user_id):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("injected failure after the first seat was removed")
        return original(seat_id, user_id)

    monkeypatch.setattr(
        student_deletion_module, "remove_student_from_teacher_scope", fail_on_the_second
    )

    response = _bulk_delete(client, targets, "DELETE STUDENTS")
    assert response.status_code == 500
    assert response.get_json()["message"] == (
        "Could not delete the selected students. Nothing was deleted."
    )
    # The first seat's removal really was attempted before the failure.
    assert calls["n"] == 2

    db.session.expire_all()
    assert sorted(_student_seat_ids(classroom.class_id)) == sorted(seat_ids)
