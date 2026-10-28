"""No log call prints `classes.class_id`, `seats.id` or `users.id` (DOM-OPS-001 §7).

Owner ruling 2026-10-27: an internal identity printed in a log is a data leak.
Production lines carried the internal class id on every request and seat ids in
messages such as ``DASHBOARD DEBUG: Student 211``.
"""
from pathlib import Path

import pytest

from tests.guards.internal_identity_in_logs import find_violations

ROOT = Path(__file__).resolve().parents[1]
SCANNED = sorted((ROOT / "app").rglob("*.py")) + [ROOT / "wsgi.py"]


def test_DOM_OPS_001__no_log_call_reads_an_internal_identity():
    violations = [
        f"{v.path}:{v.line}: {v.expression}"
        for path in SCANNED
        for v in find_violations(path.read_text(encoding="utf-8"), str(path.relative_to(ROOT)))
    ]
    assert violations == []


@pytest.mark.parametrize("line", [
    'current_app.logger.info("DASHBOARD DEBUG: Student %s", student.id)',
    'logger.info("TAP success - seat %s class_id=%s", seat_id, class_id)',
    'current_app.logger.warning(f"TAP ERROR: Invalid PIN for student {student_user.id}")',
    'current_app.logger.info("pass %s", getattr(student, "id", None))',
    'current_app.logger.error("x", extra={"class_id": context.get("class_id")})',
    'logger.warning("seat %s", row["seat_id"])',
    'logging.getLogger(__name__).exception("failed for user_id=%s", user_id)',
    'logger.info(f"FEAT-ENTRY: correlation_id={self.correlation_id}")',
    'logger.info("key %s", idempotency_key)',
    'logger.info("seats=%s", ",".join(str(seat_id) for seat_id in seat_ids))',
])
def test_DOM_OPS_001__detector_reports_each_spelling_of_a_leak(line):
    assert find_violations(line), line


@pytest.mark.parametrize("line", [
    'logger.info("seat %s", seat.public_id)',
    'logger.info("class %s", class_log_ref(class_id))',
    'logger.info("seat %s", seat_log_ref(seat_id))',
    'logger.info("seats=%s", ",".join(seat_log_ref(seat_id) for seat_id in seat_ids))',
    'logger.info("key %s", loggable_token(idempotency_key))',
    'logger.info("own pass %s", log_entry.requested_by_seat_id == student.id)',
    'logger.warning("key length %s", len(self.idempotency_key))',
    'logger.info("join code %s", display_join_code)',
])
def test_DOM_OPS_001__detector_accepts_public_forms(line):
    assert find_violations(line) == [], line


def test_DOM_OPS_001__request_log_lines_name_the_class_by_its_public_id(client, app):
    """The production format and filter, on a real student request."""
    import io
    import logging

    from tests.helpers.classroom_initializer import initialize_as_student

    from app import DEFAULT_LOG_FORMAT, RequestIdFilter

    classroom, student = initialize_as_student("chemistry_p1", client, app)
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(logging.Formatter(DEFAULT_LOG_FORMAT))
    handler.addFilter(RequestIdFilter())
    app.logger.addHandler(handler)
    try:
        assert client.get("/student/dashboard").status_code == 200
    finally:
        app.logger.removeHandler(handler)

    lines = [line for line in buffer.getvalue().splitlines() if student.seat.public_id in line]
    assert lines, "the request wrote no attributed log line"
    with app.app_context():
        from app.models import ClassEconomy
        class_public_id = ClassEconomy.query.get(classroom.class_id).class_public_id
    output = "\n".join(lines)
    assert f"class_public_id={class_public_id}" in output
    assert classroom.class_id not in output
    assert f"Student {student.seat.id} " not in output


CLASS_ID = "d478db0f-0ce3-42e1-b7c4-905b57f092ec"


@pytest.mark.parametrize("value,label", [
    (f"prod_attendance:{CLASS_ID}:211:start_work:ab", "prod_attendance"),
    (f"corr_support_issue_{CLASS_ID}_6aed8896", "corr_support_issue"),
    (f"savings-interest-job:{CLASS_ID}:2026-10-27", "savings-interest-job"),
    (CLASS_ID, ""),  # a bare id keeps no label, not even its first letter
])
def test_DOM_OPS_001__loggable_token_keeps_the_label_and_drops_the_identity(value, label):
    from app.utils.helpers import loggable_token

    rendered = loggable_token(value)
    assert rendered.startswith(f"{label}#")
    assert CLASS_ID not in rendered and "211" not in rendered
    assert rendered == loggable_token(value)  # stable, so it still matches the stored key


def test_DOM_OPS_001__loggable_token_passes_random_correlation_ids_through():
    from app.utils.helpers import loggable_token

    assert loggable_token("corr_6877a79fe7f048f3a995fa3456a6fbe3") == "corr_6877a79fe7f048f3a995fa3456a6fbe3"
    assert loggable_token(None) == "NONE"


def test_DOM_OPS_001__log_refs_survive_an_aborted_transaction(app):
    """Log references run in exception handlers, after the failure they report.

    A failed statement aborts the PostgreSQL transaction; a lookup must then
    degrade to "-" rather than raise a second error over the original one.
    """
    import sqlalchemy as sa

    from app import db
    from app.services.tlcp import class_log_ref, seat_log_ref
    from tests.helpers.classroom_initializer import initialize

    classroom = initialize("chemistry_p1", app)
    seat_id = classroom.students[0].seat.id
    with app.app_context():
        with pytest.raises(sa.exc.DBAPIError):
            db.session.execute(sa.text("SELECT 1/0"))
        assert class_log_ref(classroom.class_id) == "-"
        assert seat_log_ref(seat_id) == "-"
        db.session.rollback()
        assert class_log_ref(classroom.class_id) != "-"
        assert seat_log_ref(seat_id) == classroom.students[0].seat.public_id
