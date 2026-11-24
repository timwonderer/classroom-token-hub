"""A failed statement's exception text carries the SQL, never its bound values (INV-ARC-005 §V).

Without ``hide_parameters`` SQLAlchemy appends ``[parameters: {...}]`` to every
``StatementError``. That text reaches logs through ``logger.exception(...)`` and
through f-strings that interpolate the exception, and bound values include
plaintext free text (support tickets, claim explanations, notes) and internal
ids that must stay inside the database (DOM-OPS-001 §7).

The failure is a runtime division by zero because its Postgres message carries
neither a ``LINE 1:`` excerpt nor a ``DETAIL`` row: psycopg2 interpolates values
client-side, so a parse-position error (or a ``Failing row contains`` /
``Key (...)=(...)`` detail) echoes them from the server, which
``hide_parameters`` cannot reach. Here only SQLAlchemy's parameter dump could.
"""

from __future__ import annotations

import logging

import pytest
from sqlalchemy import text
from sqlalchemy.exc import StatementError

from app.extensions import db

SENTINEL = "zz-sentinel-free-text-7f3c"


def test_INV_ARC_005__logged_statement_error_omits_bound_values(app, caplog):
    logger = logging.getLogger("test.sql_error_text")
    with app.app_context():
        with pytest.raises(StatementError) as raised:
            db.session.execute(
                text("SELECT CAST(:note AS text) WHERE 1 / 0 = 1"),
                {"note": SENTINEL},
            )
        db.session.rollback()

        with caplog.at_level(logging.ERROR):
            try:
                raise raised.value
            except StatementError as exc:
                logger.exception("statement failed — %s", exc)

    assert "1 / 0" in str(raised.value)
    formatted = "\n".join(logging.Formatter().format(r) for r in caplog.records)
    assert "1 / 0" in formatted
    assert SENTINEL not in formatted


def test_INV_ARC_005__failed_issue_submission_logs_no_student_text(client, app, caplog, monkeypatch):
    """Postgres's own ``DETAIL: Failing row contains (...)`` reaches ``str(exc)``
    whatever ``hide_parameters`` says, so a free-text write path logs the
    exception class only."""
    from app.models import IssueCategory
    from app.utils import issue_helpers
    from tests.helpers.classroom_initializer import initialize_as_student

    initialize_as_student("chemistry_p1", client, app)
    with app.app_context():
        category = IssueCategory.query.filter_by(is_active=True, category_type="general").first()
        assert category is not None, "migrations seed the general issue categories"
        category_id = category.id

    def _fail(**kwargs):
        raise RuntimeError(f"DETAIL: Failing row contains ({kwargs['explanation']}, null).")

    monkeypatch.setattr(issue_helpers, "create_issue", _fail)
    with caplog.at_level(logging.ERROR):
        response = client.post(
            "/student/help-support/submit-issue",
            data={"category_id": category_id, "explanation": SENTINEL},
        )

    assert response.status_code == 200
    messages = "\n".join(r.getMessage() for r in caplog.records)
    assert "Error submitting issue: RuntimeError" in messages
    assert SENTINEL not in messages
