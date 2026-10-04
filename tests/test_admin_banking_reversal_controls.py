"""Banking displays only the pure, domain-authorized reversal controls."""

from bs4 import BeautifulSoup

from app.extensions import db
from app.feats.base import FEATContext
from app.models import AuditEvent, Transaction
from app.services.ledger_correction_service import reverse_transaction
from tests.dom.interpretation.helpers import unused_store_purchase
from tests.helpers.classroom_initializer import initialize_as_teacher


def _banking_page(client):
    before = (Transaction.query.count(), AuditEvent.query.count())
    response = client.get("/admin/banking")
    assert response.status_code == 200
    assert (Transaction.query.count(), AuditEvent.query.count()) == before
    return BeautifulSoup(response.get_data(as_text=True), "html.parser")


def _reversal_control(page, transaction):
    return page.find("button", attrs={"onclick": f"voidTransaction({transaction.id})"})


def test_banking_reverse_control_requires_eligible_purchase_and_hides_compensated_rows(client, app):
    """GET never offers reversal for a reversed original or compensation child."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    purchase = unused_store_purchase(classroom, student, key="banking-controls")
    facts = (purchase.amount, purchase.correlation_id, purchase.lineage_token)
    page = _banking_page(client)
    assert _reversal_control(page, purchase) is not None
    for other in Transaction.query.filter(Transaction.id != purchase.id).all():
        assert _reversal_control(page, other) is None

    with FEATContext("FEAT-LED-002", correlation_id=purchase.correlation_id,
                     idempotency_key="banking-controls:refund"):
        reversal = reverse_transaction(
            purchase, description="Banking control regression refund",
            idempotency_key="banking-controls:refund",
            actor_seat_id=classroom.teacher_seat.id,
            compensation_type="refund",
        )
    db.session.refresh(purchase)
    assert reversal.type == "REVERSAL"
    assert reversal.original_transaction_id == purchase.id
    assert reversal.correlation_id == purchase.correlation_id
    assert purchase.reversal_transaction_id is None
    assert (purchase.amount, purchase.correlation_id, purchase.lineage_token) == facts

    page = _banking_page(client)
    assert _reversal_control(page, purchase) is None
    assert _reversal_control(page, reversal) is None
    assert page.find_all("button", attrs={"title": "Reverse transaction"}) == []
