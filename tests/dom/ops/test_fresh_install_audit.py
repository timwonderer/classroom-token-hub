"""Fresh-install lineage acceptance (DOM-OPS-002 §§6.2C, 6.3 and 8.3)."""
from app.extensions import db
from app.models import AuditEvent, ChainHead, PayrollEvent, Transaction
from app.utils.audit_verifier import verified_creation_evidences
from tests.helpers.class_domain import manual_payroll
from tests.helpers.classroom_initializer import initialize_as_teacher


def test_first_manual_credit_authenticates_payload_and_complete_class_head(client, app):
    assert AuditEvent.query.count() == 0
    for head in ChainHead.query.all():
        assert (head.chain_scope, head.latest_sequence, head.event_count) == ("system", 0, 0)

    classroom = initialize_as_teacher("chemistry_p1", client, app, with_payroll_settings=False)
    class_id = classroom.class_id
    scope = f"class:{class_id}"
    seat = classroom.students[0].seat
    assert db.session.get(ChainHead, scope) is None

    response = manual_payroll(client, student_ids=[seat.public_id], description="Audit acceptance", amount="12.50")
    assert response.status_code == 302
    credit = Transaction.query.filter_by(class_id=class_id, seat_id=seat.id, type="manual_payment").one()
    payroll = PayrollEvent.query.filter_by(class_id=class_id, target_seat_id=seat.id, payroll_event_type="manual_credit").one()
    payroll_event = db.session.get(AuditEvent, payroll.lineage_event_id)
    assert payroll_event.feat_id == "FEAT-PROD-003"

    events = AuditEvent.query.filter_by(chain_scope=scope).order_by(AuditEvent.sequence_number).all()
    head = db.session.get(ChainHead, scope)
    assert len(events) >= 2
    assert events[0].previous_hash == "genesis"
    assert (head.latest_sequence, head.event_count, head.latest_hash) == (
        events[-1].sequence_number, len(events), events[-1].event_hash,
    )

    # An empty batch carries no row proof, even when the class has a real head.
    assert verified_creation_evidences([], class_id).evidence == ()
    items = [("ledger_transaction", credit)]
    prefix = verified_creation_evidences(items, class_id, max_chain_events=1)
    assert (prefix.chain_status, prefix.reason, prefix.evidence) == ("UNAVAILABLE", "EVIDENCE_LIMIT_EXCEEDED", (None,))

    result = verified_creation_evidences(items, class_id, required_fields=("amount_cents",))
    assert result.chain_status == "COMPLETE"
    proof, = result.evidence
    assert proof is not None
    assert (proof.class_id, proof.row_pk) == (class_id, str(credit.id))
    assert (proof.lineage_event_id, proof.lineage_token) == (credit.lineage_event_id, credit.lineage_token)
    assert dict(proof.protected_values)["amount_cents"] == 1250
