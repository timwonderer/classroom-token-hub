"""Regression for F6c/F10: an unknown transfer account name must not 500.

`from_account`/`to_account` are only constrained by the <select> options in
templates/student_transfer.html — client-side only. A crafted POST naming any
other string reached execute_account_transfer() -> get_available_balance(),
which deliberately raises ValueError for an account_type outside
{"checking", "savings"} (ledger_balance_query_service.py's
_require_balance_scope, by design, since silently answering a different
question is worse than failing). Nothing in the route caught that ValueError,
so it became an uncaught exception and an HTTP 500 instead of an ordinary
"invalid request" response. The fix validates the account names before any
balance read or FEAT call.
"""

from __future__ import annotations

from app.extensions import db
from app.models import Transaction
from tests.helpers.classroom_initializer import initialize_as_student


def test_transfer_with_unknown_from_account_is_rejected_not_500(client, app):
    classroom, student = initialize_as_student("chemistry_p1", client, app)
    class_id = classroom.class_id

    with client.session_transaction() as sess:
        sess["transfer_token"] = "test-token"

    # CodeRabbit review: a brand-new student has $0.00 checking, so a plain
    # "did it redirect?" assertion also passes when the $10 transfer is
    # rejected for insufficient funds — before the account-name guard ever
    # runs — proving nothing about this fix. Following the redirect and
    # asserting the guard's own flashed message is what actually requires it.
    resp = client.post(
        "/student/transfer",
        data={
            "from_account": "bitcoin",
            "to_account": "savings",
            "amount": "10.00",
            "transfer_token": "test-token",
            "pin": student.pin,
        },
        follow_redirects=True,
    )

    assert resp.status_code != 500
    assert b"Invalid account selection." in resp.data

    with app.app_context():
        assert Transaction.query.filter_by(class_id=class_id, seat_id=student.seat.id).count() == 0


def test_transfer_with_unknown_to_account_is_rejected_not_500(client, app):
    classroom, student = initialize_as_student("chemistry_p1", client, app)
    class_id = classroom.class_id

    with client.session_transaction() as sess:
        sess["transfer_token"] = "test-token"

    resp = client.post(
        "/student/transfer",
        data={
            "from_account": "checking",
            "to_account": "vault",
            "amount": "10.00",
            "transfer_token": "test-token",
            "pin": student.pin,
        },
        follow_redirects=True,
    )

    assert resp.status_code != 500
    assert b"Invalid account selection." in resp.data

    with app.app_context():
        assert Transaction.query.filter_by(class_id=class_id, seat_id=student.seat.id).count() == 0


def test_transfer_with_unknown_account_json_returns_400_with_message(client, app):
    classroom, student = initialize_as_student("chemistry_p1", client, app)

    with client.session_transaction() as sess:
        sess["transfer_token"] = "test-token"

    resp = client.post(
        "/student/transfer",
        data={
            "from_account": "checking; DROP TABLE users;",
            "to_account": "savings",
            "amount": "10.00",
            "transfer_token": "test-token",
            "pin": student.pin,
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
        follow_redirects=False,
    )

    assert resp.status_code == 400
    assert resp.get_json()["status"] == "error"
