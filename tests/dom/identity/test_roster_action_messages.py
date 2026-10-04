"""Roster import and unclaim echo only vetted messages to the teacher (CodeQL py/stack-trace-exposure)."""
import ast
import inspect

import pytest

from app.feats import identity_feat
from app.feats.identity_feat import ROSTER_ACTION_MESSAGES, roster_action_message
from tests.helpers.classroom_initializer import initialize_as_teacher

LEAK = "internal detail: relation seats violates constraint"


def _raised_literals(source):
    """Constant messages of every direct ``raise ValueError(...)`` in ``source``.

    Parsed rather than pattern-matched so single-quoted, adjacent and multiline
    literals are all seen; a non-constant message is a failure, not a skip.
    """
    raised = set()
    for node in ast.walk(ast.parse(source)):
        error = node.exc if isinstance(node, ast.Raise) else None
        if not (isinstance(error, ast.Call) and isinstance(error.func, ast.Name)
                and error.func.id == "ValueError"):
            continue
        assert len(error.args) == 1, ast.dump(error)
        message = error.args[0]
        assert isinstance(message, ast.Constant) and isinstance(message.value, str), ast.dump(error)
        raised.add(message.value)
    return raised


def test_roster_action_message_returns_vetted_text_for_known_messages():
    for message in ROSTER_ACTION_MESSAGES:
        assert roster_action_message(ValueError(message), "fallback") == message


def test_roster_action_message_hides_unvetted_text():
    assert roster_action_message(ValueError(LEAK), "fallback") == "fallback"


def test_feat_value_errors_are_all_vetted_messages():
    """A new ValueError in these FEATs must be added to the vetted set or it is hidden."""
    raised = (_raised_literals(inspect.getsource(identity_feat.import_student_seats))
              | _raised_literals(inspect.getsource(identity_feat.unclaim_student_seat)))
    assert raised, "detector found no raise statements"
    assert raised <= ROSTER_ACTION_MESSAGES, raised - ROSTER_ACTION_MESSAGES


def test_raise_detector_reports_a_near_miss_message():
    synthetic = ("def f():\n    raise ValueError('A brand new '\n                     'teacher message.')\n")
    assert _raised_literals(synthetic) == {"A brand new teacher message."}
    assert not _raised_literals(synthetic) <= ROSTER_ACTION_MESSAGES


def test_raise_detector_rejects_a_non_constant_message():
    with pytest.raises(AssertionError):
        _raised_literals("def f(detail):\n    raise ValueError(f'bad {detail}')\n")


def test_upload_students_keeps_a_vetted_validation_message(client, app):
    initialize_as_teacher("chemistry_p1", client, app)
    response = client.post("/admin/upload-students", json={"students": [{"first_name": "", "last_name": "Rivera"}]})
    assert response.status_code == 400
    assert response.get_json()["message"] == "Every row needs a first and last name."


def test_upload_students_hides_unexpected_error_text(client, app, monkeypatch):
    initialize_as_teacher("chemistry_p1", client, app)

    def boom(**_kwargs):
        raise ValueError(LEAK)

    monkeypatch.setattr(identity_feat, "import_student_seats", boom)
    response = client.post("/admin/upload-students", json={"students": [{"first_name": "Ana", "last_name": "Rivera"}]})
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert LEAK not in body
    assert response.get_json()["message"] == "Student import could not be completed."


def test_unclaim_keeps_a_vetted_stale_roster_message(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    seat = classroom.students[0].seat
    response = client.post("/admin/student/unclaim", json=dict(
        seat_id=seat.id, claim_generation=seat.claim_generation + 5,
        first_name="Fresh", last_name="Claim", confirmation="UNCLAIM"))
    assert response.status_code == 400
    assert response.get_json()["message"] == "The seat's claim has changed. Refresh the roster before unclaiming it."


def test_unclaim_hides_unexpected_error_text(client, app, monkeypatch):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    seat = classroom.students[0].seat

    def boom(**_kwargs):
        raise ValueError(LEAK)

    monkeypatch.setattr(identity_feat, "unclaim_student_seat", boom)
    response = client.post("/admin/student/unclaim", json=dict(
        seat_id=seat.id, claim_generation=seat.claim_generation,
        first_name="Fresh", last_name="Claim", confirmation="UNCLAIM"))
    assert response.status_code == 400
    assert LEAK not in response.get_data(as_text=True)
    assert response.get_json()["message"] == "Unclaim could not be completed."
