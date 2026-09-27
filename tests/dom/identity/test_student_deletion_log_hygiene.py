"""Regression: student deletion must keep decrypted names out of the log.

The failure path once logged ``identity_profile.full_name``: decrypted PII in an
unencrypted, off-host-shipped application log (INV-ARC-005). That log line
lives in ``_dispatch_student_deletion``, which every roster deletion runs
through, so it is asserted here through the live roster route,
``/admin/students/bulk-delete``, against real emitted log records rather than
by reading source.

A second leak, the CSRF token in the retired ``admin.delete_student`` route's
entry log, went away with that route (removed 2026-09-27, REF-API-001 §VII-D).
"""

from __future__ import annotations

import logging

from app.models import IdentityProfile
from tests.dom.identity.helpers import valid_destruction_gate
from tests.helpers.classroom_initializer import initialize_as_teacher


def _all_log_text(caplog) -> str:
    return "\n".join(r.getMessage() for r in caplog.records)


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
    import app.utils.student_deletion as student_deletion

    def _boom(*_args, **_kwargs):
        raise RuntimeError("forced failure for log-hygiene regression")

    monkeypatch.setattr(student_deletion, "remove_student_from_teacher_scope", _boom)

    with caplog.at_level(logging.ERROR):
        response = client.post(
            "/admin/students/bulk-delete",
            json={"student_ids": [seat_id], **valid_destruction_gate("DELETE STUDENTS")},
        )

    assert response.status_code == 500, "the forced failure did not reach the error path"
    text = _all_log_text(caplog)
    assert "Error deleting student" in text, "failure path did not log at all"
    assert full_name not in text, "student full name reached the application log"
    assert first_name not in text, "student first name reached the application log"
    assert f"seat_id={seat_id}" in text, "log must still identify the seat"
