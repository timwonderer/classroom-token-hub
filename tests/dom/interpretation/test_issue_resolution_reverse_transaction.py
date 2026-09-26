from decimal import Decimal

from app.extensions import db
from app.feats.base import FEATContext
from app.models import EntitlementEvent, Transaction
from app.services import entitlement_service
from app.services.ledger_balance_query_service import get_available_balance
from tests.dom.interpretation.helpers import (
    issue_for_transaction,
    issue_reverse_scope_mismatch_state,
    issue_reverse_success_state,
    unused_store_purchase,
)
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.helpers.ledger import create_ledger_idempotent_transaction
from app.utils.opaque_refs import make_opaque_ref


def _grants(tx):
    return EntitlementEvent.query.filter_by(
        class_id=tx.class_id,
        target_seat_id=tx.seat_id,
        correlation_id=tx.correlation_id,
        event_type="GRANTED",
    ).all()


def _revocations(tx):
    return EntitlementEvent.query.filter_by(
        class_id=tx.class_id,
        correlation_id=tx.correlation_id,
        event_type="REVOKED",
    ).all()


def test_DOM_SUP_001__issue_reverse_transaction_creates_reversal_for_unused_purchase(client, app):
    """In-scope reversal: submitter owns the referenced unused Store purchase
    and the teacher's active class matches the issue's class, so the reversal
    succeeds and the item is revoked."""
    classroom, student, issue, tx = issue_reverse_success_state(client, app)
    status_before = tx.status

    issue_ref = make_opaque_ref("issue", issue.id)
    page = client.get(f"/admin/issues/{issue_ref}").get_data(as_text=True)
    assert 'value="reverse_transaction"' in page
    assert 'value="refund_transaction"' in page

    response = client.post(
        f"/admin/issues/{issue_ref}/resolve",
        data={"action_type": "reverse_transaction", "teacher_notes": "Valid request"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    db.session.refresh(tx)
    # The original stays a standing historical fact. A reversal may not present
    # it as never having occurred (SPEC-OPS-001 §3.2), and money is not voided
    # at all (INV-OPS-001) — only the link forward to the reversal is added.
    assert tx.status == status_before
    assert tx.reversal_transaction_id is not None

    reversal = db.session.get(Transaction, tx.reversal_transaction_id)
    assert reversal is not None
    assert reversal.original_transaction_id == tx.id
    assert reversal.class_id == classroom.class_id
    assert reversal.amount == Decimal("30.00")
    assert reversal.correlation_id == tx.correlation_id
    assert {event.entitlement_id for event in _revocations(tx)} == {
        grant.entitlement_id for grant in _grants(tx)
    }


def test_DOM_SUP_001__issue_refund_retains_the_item(client, app):
    classroom, student, issue, tx = issue_reverse_success_state(client, app)

    response = client.post(
        f"/admin/issues/{make_opaque_ref('issue', issue.id)}/resolve",
        data={"action_type": "refund_transaction"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    db.session.refresh(tx)
    assert tx.reversal_transaction_id is not None
    assert _revocations(tx) == []


def test_DOM_SUP_001__issue_reverse_transaction_rejects_scope_mismatch(client, app):
    """Ownership-mismatch rejection: the issue is visible under the teacher's
    active class (no 404), but the referenced transaction belongs to a different
    seat than the submitter, so the reversal is rejected and the transaction is
    left untouched."""
    classroom, submitter, other_student, issue, tx = issue_reverse_scope_mismatch_state(client, app)

    # Sanity: the rejection must be driven by the intended ownership mismatch,
    # not by issue invisibility or an active-class mismatch.
    submitter_seat_id = submitter.seat.id
    assert tx.seat_id == other_student.seat.id
    assert tx.seat_id != submitter_seat_id
    assert issue.class_public_id == classroom.economy.class_public_id

    issue_ref = make_opaque_ref("issue", issue.id)

    # The issue detail page is reachable (visible in the active class scope):
    # confirms the rejection below is not merely a 404 from scope filtering.
    view_response = client.get(f"/admin/issues/{issue_ref}")
    assert view_response.status_code == 200

    response = client.post(
        f"/admin/issues/{issue_ref}/resolve",
        data={"action_type": "reverse_transaction", "teacher_notes": "Attempt mismatch"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert f"/admin/issues/{issue_ref}" in response.location

    db.session.refresh(tx)
    assert tx.reversal_transaction_id is None


def test_SPEC_OPS_001__payroll_cannot_be_reversed_or_refunded_from_an_issue(client, app):
    """Absence of a prohibition is not authorization (SPEC-OPS-001 §3.7).

    Refunding a positive payroll credit posted a negative reversal and debited
    the student, because the route never asked what kind of transaction it was.
    """
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="issue-payroll:seed"):
        payroll, _ = create_ledger_idempotent_transaction(
            idempotency_key="issue-payroll-seed",
            seat_id=student.seat.id,
            class_id=classroom.class_id,
            amount=Decimal("25.00"),
            account_type="checking",
            type="payroll",
            description="Payroll",
        )
    db.session.commit()
    issue = issue_for_transaction(classroom, student, payroll, key="issue-payroll")
    issue_ref = make_opaque_ref("issue", issue.id)
    balance_before = get_available_balance(student.seat.id, classroom.class_id, "checking")

    page = client.get(f"/admin/issues/{issue_ref}").get_data(as_text=True)
    assert 'value="refund_transaction"' not in page
    assert 'value="reverse_transaction"' not in page
    assert 'value="manual_adjustment"' in page

    for action in ("refund_transaction", "reverse_transaction"):
        response = client.post(
            f"/admin/issues/{issue_ref}/resolve",
            data={"action_type": action},
            follow_redirects=False,
        )
        assert response.status_code == 302

    db.session.refresh(payroll)
    assert payroll.reversal_transaction_id is None
    assert Transaction.query.filter_by(original_transaction_id=payroll.id).count() == 0
    assert get_available_balance(student.seat.id, classroom.class_id, "checking") == balance_before


def test_DOM_SUP_001__used_item_cannot_be_reversed_or_refunded(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    tx = unused_store_purchase(classroom, student, key="issue-used-item")
    grant = _grants(tx)[0]
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="issue-used-item:consume"):
        entitlement_service.consume_entitlement(
            entitlement_id=grant.entitlement_id,
            class_id=grant.class_id,
            target_seat_id=grant.target_seat_id,
            actor_seat_id=grant.target_seat_id,
            product_id=grant.product_id,
            entitlement_type=grant.entitlement_type,
            acquisition_type=grant.acquisition_type,
            correlation_id=grant.correlation_id,
        )
    db.session.commit()
    issue = issue_for_transaction(classroom, student, tx, key="issue-used-item")
    issue_ref = make_opaque_ref("issue", issue.id)

    assert 'value="reverse_transaction"' not in client.get(f"/admin/issues/{issue_ref}").get_data(as_text=True)
    response = client.post(
        f"/admin/issues/{issue_ref}/resolve",
        data={"action_type": "refund_transaction"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    db.session.refresh(tx)
    assert tx.reversal_transaction_id is None
