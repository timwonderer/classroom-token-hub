"""Regression: the student-deletion route must keep secrets out of the log.

Two leaks lived in ``admin.delete_student``:

1. The failure path logged ``identity_profile.full_name`` — decrypted PII in an
   unencrypted, off-host-shipped application log (INV-ARC-005; see
   ``.claude/rules/security.md``, "Sensitive Data Exposure").
2. The entry log dumped ``dict(request.form)`` wholesale, which put the
   session-bound CSRF token into the same log.

Both are asserted here against real emitted log records, not by reading source.
The flash messages deliberately still carry the student's name: those are shown
to the authenticated teacher who owns the class, which is authorized display.
"""

from __future__ import annotations

import logging

import pytest

from app import db
from app.models import IdentityProfile
from tests.helpers.classroom_initializer import initialize_as_teacher


def _delete_form(seat_id: int) -> dict:
    return {"seat_id": str(seat_id), "confirmation": "DELETE"}


def _all_log_text(caplog) -> str:
    return "\n".join(r.getMessage() for r in caplog.records)


def test_delete_student_entry_log_omits_csrf_token(client, caplog):
    """The entry log records which fields arrived, never their values."""
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    seat = classroom.students[0].seat

    sentinel = "csrf-token-sentinel-2f9a4c"
    with caplog.at_level(logging.INFO):
        client.post(
            "/admin/student/delete",
            data={**_delete_form(seat.id), "csrf_token": sentinel},
            follow_redirects=True,
        )

    text = _all_log_text(caplog)
    assert "Delete student route accessed" in text, "entry log did not fire"
    assert sentinel not in text, "CSRF token value reached the application log"
    # The field *names* remain, so the diagnostic keeps its value.
    assert "seat_id" in text


def test_delete_student_failure_log_omits_student_pii(client, caplog, monkeypatch):
    """When deletion raises, the log identifies the seat, never the student."""
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    student = classroom.students[0]
    seat_id = student.seat.id

    profile = IdentityProfile.query.filter_by(seat_id=seat_id).first()
    assert profile is not None
    first_name = profile.first_name
    full_name = profile.full_name
    assert first_name, "fixture must provide a decryptable name to leak"

    # Force the failure path that previously logged the name.
    import app.routes.admin as admin_routes

    def _boom(*_args, **_kwargs):
        raise RuntimeError("forced failure for log-hygiene regression")

    monkeypatch.setattr(admin_routes, "_remove_student_from_teacher_scope", _boom)

    with caplog.at_level(logging.ERROR):
        client.post(
            "/admin/student/delete",
            data=_delete_form(seat_id),
            follow_redirects=True,
        )

    text = _all_log_text(caplog)
    assert "Error deleting student" in text, "failure path did not log at all"
    assert full_name not in text, "student full name reached the application log"
    assert first_name not in text, "student first name reached the application log"
    assert f"seat_id={seat_id}" in text, "log must still identify the seat"
