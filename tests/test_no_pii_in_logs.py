"""Logs carry seat and class ids, never a student's name (INV-ARC-005 §V).

On 2026-10-02 the production journal showed one line per student for every
bulk hall-pass adjustment, each carrying the student's full name — decrypted
from ``identity_profiles``, whose names are stored with ``PIIEncryptedType``
precisely so they never sit in plaintext (INV-ARC-018). The route now logs
``seat_id`` and ``class_id``; attribution by id is what INV-ARC-018 prescribes
for audit records as well.

Two layers: a behavioural regression on the route that shipped the defect, and
a structural guard over ``app/`` so the next logger call cannot read a name off
the profile either.
"""

from __future__ import annotations

import logging
from pathlib import Path

from tests.guards.pii_in_log_calls import count_logger_calls, find_pii_in_log_calls
from tests.helpers.classroom_initializer import initialize_as_teacher

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = REPO_ROOT / "app"


# --------------------------------------------------------------------------
# Behavioural regression — the route that shipped the defect
# --------------------------------------------------------------------------

def test_bulk_hall_pass_adjustment_logs_seat_and_class_not_name(client, app, caplog):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]

    with caplog.at_level(logging.INFO):
        response = client.post(
            "/admin/students/bulk-adjust-hall-pass-entitlements",
            json={"student_ids": [student.seat_id], "update_type": "add", "value": 2},
        )

    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()["status"] == "success"

    lines = [r.getMessage() for r in caplog.records if "hall pass entitlements" in r.getMessage()]
    assert len(lines) == 1, lines
    line = lines[0]
    assert f"seat_id={student.seat_id}" in line
    assert f"class_id={classroom.class_id}" in line

    every_message = "\n".join(r.getMessage() for r in caplog.records)
    assert student.first_name not in every_message
    assert student.last_name not in every_message


# --------------------------------------------------------------------------
# Structural guard
# --------------------------------------------------------------------------

def _app_sources() -> list[Path]:
    return sorted(APP_ROOT.rglob("*.py"))


def test_no_logger_call_in_app_reads_a_name():
    violations = []
    for path in _app_sources():
        violations += find_pii_in_log_calls(
            path.read_text(encoding="utf-8"), str(path.relative_to(REPO_ROOT))
        )

    assert not violations, (
        "logger calls that read a student's name — logs must carry no PII "
        "(INV-ARC-005 §V). Log seat_id and class_id instead:\n  "
        + "\n  ".join(str(v) for v in violations)
    )


def test_guard_still_recognises_the_app_logger_calls():
    """SOP-TEST-003 §IX.A(4): a rename of the logger must not turn the guard off."""
    total = sum(count_logger_calls(p.read_text(encoding="utf-8")) for p in _app_sources())
    assert total > 200, f"guard recognised only {total} logger calls in app/"

    admin = (APP_ROOT / "routes" / "admin.py").read_text(encoding="utf-8")
    assert count_logger_calls(admin) > 0


# --------------------------------------------------------------------------
# Mutation proofs — SOP-TEST-003 §IX.A
# --------------------------------------------------------------------------

def test_detector_reports_the_shipped_hall_pass_line_verbatim():
    shipped = '''
def bulk():
    current_app.logger.info(
        f"Admin adjusted hall pass entitlements for student {student.id} ({student.identity_profile.full_name if student.identity_profile else 'unknown'}): {update_type} {value}, new value: {new_value}"
    )
'''
    violations = find_pii_in_log_calls(shipped)
    assert len(violations) == 1
    assert violations[0].line == 3


def test_detector_reports_percent_style_args():
    """The lazy-format spelling, which a check of f-strings alone would miss."""
    source = 'logger.info("seat %s (%s)", seat.id, profile.first_name)\n'
    assert [v.field for v in find_pii_in_log_calls(source)] == ["first_name"]


def test_detector_reports_names_passed_through_extra():
    source = 'app.logger.warning("claim failed", extra={"who": seat.identity_profile.last_name})\n'
    assert len(find_pii_in_log_calls(source)) == 1


def test_detector_reports_a_name_held_in_a_local():
    source = 'full_name = profile.full_name\nlogger.error("adjusted %s", full_name)\n'
    violations = find_pii_in_log_calls(source)
    assert [v.line for v in violations] == [2]


def test_detector_reports_any_receiver_name():
    """Shape, not variable names: ``_probe.first_name`` is caught like ``profile.first_name``."""
    source = 'logging.getLogger(__name__).info(f"{_probe_profile.first_name}")\n'
    assert len(find_pii_in_log_calls(source)) == 1


def test_detector_reports_format_calls_and_last_initial():
    source = 'self._log.debug("{} {}".format(seat.id, p.last_initial))\n'
    assert len(find_pii_in_log_calls(source)) == 1


def test_detector_is_quiet_on_lawful_log_lines():
    source = '''
current_app.logger.info(
    "Admin adjusted hall pass entitlements seat_id=%s class_id=%s: %s %s, new value: %s",
    student.id, student.class_id, update_type, value, new_value,
)
logger.info("class %s renamed", class_row.display_name)
logger.exception("Unhandled exception", extra={"route": request.path})
updated.append(student.identity_profile.full_name)
flash(f"Updated {profile.full_name}")
'''
    assert find_pii_in_log_calls(source) == []
