"""Teacher decisions on store redemption requests (DOM-STORE-001 §VII.B, §VIII.E.4).

A delayed-use item is redeemed by request, and asking is a use. While the
request waits there is only a pending action; the terminal event is written on
resolution. The teacher decides by the class's own norms (owner ruling
2026-10-03):

* **Approve** records ``CONSUMED`` with ``outcome = APPROVED``;
* **Deny** records ``REVOKED`` with ``outcome = DENIED``: no money moves,
  whatever way the item was acquired;
* **Return** writes no entitlement event: the item goes back unused and the
  student may ask again.

Each deletes the pending action (§VII.B), and each is final for that request.
Before this, approval imported a module that does not exist and failed with a
500 on every request, and denial left the pending row stamped ``REJECTED``.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.store_purchase_feat import execute_store_purchase
from app.models import EntitlementEvent, PendingAction, Transaction
from app.services.context_resolver import CanonicalContext
from app.services.ledger_balance_query_service import get_available_balance
from app.services.redemption_query_service import (
    list_pending_acknowledgements,
    list_pending_redemptions,
    list_resolved_redemptions,
)
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.canonical_classroom import login_student, login_teacher, provision_classroom
from tests.helpers.ledger import create_ledger_idempotent_transaction
from tests.helpers.store_products import publish_store_product

NOTE = "Reading clues from the past\nThursday"


def _fund(classroom, student, amount="500.00"):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"redeem:fund:{student.seat_id}"):
        create_ledger_idempotent_transaction(
            idempotency_key=f"redeem-fund:{student.seat_id}",
            seat_id=student.seat_id,
            class_id=classroom.class_id,
            amount=Decimal(amount),
            account_type="checking",
            type="payroll",
            description="Redemption test funding",
        )
    db.session.commit()


def _publish_delayed(classroom, name, price="150.00", **definition):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"redeem:publish:{classroom.class_id}:{name}"):
        product = publish_store_product(
            class_id=classroom.class_id,
            entitlement_type="DELAYED_USE",
            created_by_seat_id=classroom.teacher_seat_id,
            name=name,
            price=price,
            **definition,
        )
    db.session.commit()
    return product


def _buy(classroom, student, product, quantity=1):
    execute_store_purchase(
        canonical_context=CanonicalContext(
            user_id=student.user_id,
            class_id=classroom.class_id,
            seat_id=student.seat_id,
            actor_role="student",
        ),
        policy_uuid=product.policy_uuid,
        quantity=quantity,
    )
    return (
        EntitlementEvent.query.filter_by(
            class_id=classroom.class_id,
            target_seat_id=student.seat_id,
            product_id=product.product_lineage_uuid,
            event_type="GRANTED",
        )
        .order_by(EntitlementEvent.timestamp.asc(), EntitlementEvent.event_id.asc())
        .all()
    )


def _request(client, student, entitlement_id, note=NOTE):
    login_student(client, student)
    response = client.post(
        "/api/use-item",
        json={"entitlement_id": entitlement_id, "passphrase": student.passphrase, "details": note},
    )
    assert response.status_code == 200, response.data
    return PendingAction.query.filter_by(entitlement_id=entitlement_id).one()


def _terminal(entitlement_id):
    return EntitlementEvent.query.filter(
        EntitlementEvent.entitlement_id == entitlement_id,
        EntitlementEvent.event_type.in_(("CONSUMED", "EXPIRED", "REVOKED")),
    ).all()


@pytest.fixture
def requested(app, client):
    """A funded student with one $150 delayed item, redemption requested."""
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        student = classroom.students[0]
        _fund(classroom, student)
        product = _publish_delayed(classroom, "Late Work Pass", redemption_prompt="Which assignment?")
        (grant,) = _buy(classroom, student, product)
        pending = _request(client, student, grant.entitlement_id)
        yield {
            "classroom": classroom,
            "student": student,
            "product": product,
            "entitlement_id": grant.entitlement_id,
            "request_id": pending.pending_action_id,
        }


def test_pending_request_carries_the_students_note(app, requested):
    """The Details column read a key the request never wrote, so it showed '-'."""
    with app.app_context():
        (view,) = list_pending_redemptions(requested["classroom"].class_id)
        assert view.request_id == requested["request_id"]
        assert view.student_note == NOTE
        assert view.item_name == "Late Work Pass"
        assert view.redemption_prompt == "Which assignment?"
        assert view.price_paid == Decimal("150.00")


def test_approve_records_consumed_and_deletes_the_request(app, client, requested):
    classroom = requested["classroom"]
    login_teacher(client, classroom)

    response = client.post("/api/approve-redemption", json={"request_id": requested["request_id"]})

    assert response.status_code == 200, response.data
    with app.app_context():
        (terminal,) = _terminal(requested["entitlement_id"])
        assert terminal.event_type == "CONSUMED"
        assert terminal.actor_seat_id == classroom.teacher_seat_id
        assert terminal.payload["details"] == NOTE
        assert terminal.payload["pending_action_id"] == requested["request_id"]
        assert db.session.get(PendingAction, requested["request_id"]) is None

        assert list_pending_redemptions(classroom.class_id) == []
        (decided,) = list_resolved_redemptions(classroom.class_id)
        assert decided.outcome == "APPROVED"
        assert decided.request_id == requested["request_id"]
        assert decided.student_note == NOTE


def test_deny_ends_the_entitlement_without_refund(app, client, requested):
    """A redemption request is a use: denying it moves no money and voids nothing.

    Refunds and voids belong to the stage before the student asks to redeem.
    """
    classroom, student = requested["classroom"], requested["student"]
    with app.app_context():
        before = get_available_balance(student.seat_id, classroom.class_id, "checking")
    login_teacher(client, classroom)

    response = client.post(
        "/api/reject-redemption",
        json={"request_id": requested["request_id"], "note": "Assignment window closed."},
    )

    assert response.status_code == 200, response.data
    with app.app_context():
        (terminal,) = _terminal(requested["entitlement_id"])
        assert terminal.event_type == "REVOKED"
        assert terminal.payload["outcome"] == "DENIED"
        assert terminal.payload["decision_note"] == "Assignment window closed."
        assert terminal.payload["details"] == NOTE
        assert get_available_balance(student.seat_id, classroom.class_id, "checking") == before
        assert Transaction.query.filter_by(class_id=classroom.class_id, type="REVERSAL").count() == 0
        assert db.session.get(PendingAction, requested["request_id"]) is None

        (decided,) = list_resolved_redemptions(classroom.class_id)
        assert decided.outcome == "DENIED"
        assert decided.decision_note == "Assignment window closed."

        from app.services.entitlement_read_service import derive_display_status
        assert derive_display_status(requested["entitlement_id"]) == "denied"


@pytest.mark.parametrize("first, second", [
    ("/api/approve-redemption", "/api/reject-redemption"),
    ("/api/reject-redemption", "/api/approve-redemption"),
    ("/api/approve-redemption", "/api/approve-redemption"),
    ("/api/reject-redemption", "/api/return-redemption"),
    ("/api/return-redemption", "/api/reject-redemption"),
])
def test_a_decision_is_final(app, client, requested, first, second):
    login_teacher(client, requested["classroom"])
    assert client.post(first, json={"request_id": requested["request_id"]}).status_code == 200

    again = client.post(second, json={"request_id": requested["request_id"]})

    assert again.status_code == 409, again.data
    with app.app_context():
        assert len(_terminal(requested["entitlement_id"])) == (0 if first.endswith("return-redemption") else 1)
        reversals = Transaction.query.filter_by(
            class_id=requested["classroom"].class_id, type="REVERSAL",
        ).count()
        assert reversals == 0


def _checking(classroom, student):
    return get_available_balance(student.seat_id, classroom.class_id, "checking")


def _deny(client, request_id):
    return client.post("/api/reject-redemption", json={"request_id": request_id})


def _assert_denied_without_refund(classroom, student, grants, request_id, before):
    (terminal,) = _terminal(grants[0].entitlement_id)
    assert terminal.event_type == "REVOKED"
    assert terminal.payload["outcome"] == "DENIED"
    assert _checking(classroom, student) == before
    assert Transaction.query.filter_by(class_id=classroom.class_id, type="REVERSAL").count() == 0
    # Only the item the student asked to use is spent; the rest stay usable.
    for other in grants[1:]:
        assert _terminal(other.entitlement_id) == []
    assert db.session.get(PendingAction, request_id) is None


def test_any_request_can_be_denied_bulk_item(app, client):
    """However the item was acquired, the teacher may deny the request."""
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        student = classroom.students[0]
        _fund(classroom, student)
        product = _publish_delayed(
            classroom, "Late Work Pass", price="5.00",
            bulk_discount_enabled=True, bulk_discount_quantity=3, bulk_discount_percentage=20,
        )
        grants = _buy(classroom, student, product, quantity=3)
        request_id = _request(client, student, grants[0].entitlement_id).pending_action_id
        before = _checking(classroom, student)

        login_teacher(client, classroom)
        assert _deny(client, request_id).status_code == 200
        _assert_denied_without_refund(classroom, student, grants, request_id, before)


def test_any_request_can_be_denied_bundle_use(app, client):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        student = classroom.students[0]
        _fund(classroom, student)
        product = _publish_delayed(classroom, "Homework 3-Pack", price="30.00", is_bundle=True, bundle_quantity=3)
        grants = _buy(classroom, student, product, quantity=1)
        assert len(grants) == 3
        request_id = _request(client, student, grants[0].entitlement_id).pending_action_id
        before = _checking(classroom, student)

        (view,) = list_pending_redemptions(classroom.class_id)
        assert view.bundle_size == 3

        login_teacher(client, classroom)
        assert _deny(client, request_id).status_code == 200
        _assert_denied_without_refund(classroom, student, grants, request_id, before)


def test_same_teacher_other_period_cannot_decide(app, client):
    """Owning both classes is not scope: the request is decided from its own class."""
    with app.app_context():
        home = provision_classroom("chemistry_p1")
        other = provision_classroom("ap_csp_p3")
        assert home.teacher_user_id == other.teacher_user_id
        student = other.students[0]
        _fund(other, student)
        product = _publish_delayed(other, "Late Work Pass")
        (grant,) = _buy(other, student, product)
        request_id = _request(client, student, grant.entitlement_id).pending_action_id

        assert list_pending_redemptions(home.class_id) == []

        login_teacher(client, home)
        for url in ("/api/approve-redemption", "/api/reject-redemption"):
            response = client.post(url, json={"request_id": request_id})
            assert response.status_code == 409, response.data

        assert _terminal(grant.entitlement_id) == []
        assert db.session.get(PendingAction, request_id) is not None


def test_student_cannot_decide(app, client, requested):
    login_student(client, requested["student"])

    response = client.post("/api/approve-redemption", json={"request_id": requested["request_id"]})

    assert response.status_code in (302, 401, 403)
    with app.app_context():
        assert _terminal(requested["entitlement_id"]) == []


def test_store_page_lists_the_request_without_raw_payload(app, client, requested):
    with app.app_context():
        enable_class_feature(class_id=requested["classroom"].class_id, feature="store")
    login_teacher(client, requested["classroom"])

    response = client.get("/admin/store")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'id="redemptions-tab"' in page
    assert f'data-redemption-id="{requested["request_id"]}"' in page
    assert "Reading clues from the past" in page
    assert "Which assignment?" in page
    # The audit tab printed the pending action's payload dict verbatim.
    assert "'policy_uuid'" not in page
    assert "nothing is refunded" in page


def test_dashboard_links_each_request_to_its_review(app, client, requested):
    login_teacher(client, requested["classroom"])

    response = client.get("/admin/")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert f'/admin/store?request={requested["request_id"]}#redemptions' in page
    assert "Reading clues from the past" in page



def test_return_gives_the_item_back_unused(app, client, requested):
    classroom, student = requested["classroom"], requested["student"]
    with app.app_context():
        before = get_available_balance(student.seat_id, classroom.class_id, "checking")
    login_teacher(client, classroom)

    response = client.post("/api/return-redemption", json={"request_id": requested["request_id"]})

    assert response.status_code == 200, response.data
    with app.app_context():
        assert _terminal(requested["entitlement_id"]) == []
        assert db.session.get(PendingAction, requested["request_id"]) is None
        assert get_available_balance(student.seat_id, classroom.class_id, "checking") == before
        assert list_pending_redemptions(classroom.class_id) == []

        from app.services.entitlement_read_service import derive_display_status
        assert derive_display_status(requested["entitlement_id"]) == "purchased"

    # The request itself is closed for good.
    again = client.post("/api/approve-redemption", json={"request_id": requested["request_id"]})
    assert again.status_code == 409


def test_a_returned_item_can_be_requested_again(app, client, requested):
    classroom, student = requested["classroom"], requested["student"]
    login_teacher(client, classroom)
    assert client.post(
        "/api/return-redemption", json={"request_id": requested["request_id"]}
    ).status_code == 200

    with app.app_context():
        second = _request(client, student, requested["entitlement_id"], note="Next week instead")
        assert second.pending_action_id != requested["request_id"]
        (view,) = list_pending_redemptions(classroom.class_id)
        assert view.student_note == "Next week instead"

        login_teacher(client, classroom)
        assert client.post(
            "/api/approve-redemption", json={"request_id": second.pending_action_id}
        ).status_code == 200
        assert [e.event_type for e in _terminal(requested["entitlement_id"])] == ["CONSUMED"]


def test_a_waiting_request_has_no_terminal_event(app, requested):
    """During redemption there is only the pending action."""
    with app.app_context():
        assert _terminal(requested["entitlement_id"]) == []
        assert db.session.get(PendingAction, requested["request_id"]) is not None


# ---------------------------------------------------------------------------
# Immediate-use reminders (DOM-STORE-001 §VIII.E.3)
# ---------------------------------------------------------------------------


@pytest.fixture
def immediate(app):
    """A student who bought one immediate-use item."""
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        student = classroom.students[0]
        _fund(classroom, student)
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"redeem:publish-imm:{classroom.class_id}"):
            product = publish_store_product(
                class_id=classroom.class_id,
                entitlement_type="IMMEDIATE_USE",
                created_by_seat_id=classroom.teacher_seat_id,
                name="Sit Anywhere Today",
                price="8.00",
            )
        db.session.commit()
        (grant,) = _buy(classroom, student, product)
        yield {"classroom": classroom, "student": student, "entitlement_id": grant.entitlement_id}


def test_buying_an_immediate_use_item_queues_a_reminder(app, immediate):
    with app.app_context():
        classroom = immediate["classroom"]
        (row,) = PendingAction.query.filter_by(entitlement_id=immediate["entitlement_id"]).all()
        assert row.authoritative_feat == "FEAT-STOR-002"
        assert row.payload["kind"] == "immediate_use_acknowledgement"
        assert row.class_id == classroom.class_id
        # Still used at sale; the reminder is not a request.
        assert [e.event_type for e in _terminal(immediate["entitlement_id"])] == ["CONSUMED"]
        assert list_pending_redemptions(classroom.class_id) == []
        (ack,) = list_pending_acknowledgements(classroom.class_id)
        assert ack.request_id == row.pending_action_id
        assert ack.item_name == "Sit Anywhere Today"
        assert ack.price_paid == Decimal("8.00")

        from app.services.entitlement_read_service import derive_display_status
        assert derive_display_status(immediate["entitlement_id"]) == "consumed"


def test_mark_as_complete_deletes_the_reminder_only(app, client, immediate):
    classroom = immediate["classroom"]
    with app.app_context():
        request_id = PendingAction.query.filter_by(entitlement_id=immediate["entitlement_id"]).one().pending_action_id
    login_teacher(client, classroom)

    response = client.post("/api/complete-immediate-use", json={"request_id": request_id})

    assert response.status_code == 200, response.data
    with app.app_context():
        assert db.session.get(PendingAction, request_id) is None
        assert [e.event_type for e in _terminal(immediate["entitlement_id"])] == ["CONSUMED"]
        assert list_pending_acknowledgements(classroom.class_id) == []
    again = client.post("/api/complete-immediate-use", json={"request_id": request_id})
    assert again.status_code == 409


@pytest.mark.parametrize("url", [
    "/api/approve-redemption", "/api/reject-redemption", "/api/return-redemption",
])
def test_a_reminder_is_not_a_redemption_request(app, client, immediate, url):
    """Its only resolution is Mark as complete."""
    with app.app_context():
        request_id = PendingAction.query.filter_by(entitlement_id=immediate["entitlement_id"]).one().pending_action_id
    login_teacher(client, immediate["classroom"])

    response = client.post(url, json={"request_id": request_id})

    assert response.status_code == 409, response.data
    with app.app_context():
        assert db.session.get(PendingAction, request_id) is not None


def test_same_teacher_other_period_cannot_complete(app, client, immediate):
    with app.app_context():
        other = provision_classroom("ap_csp_p3")
        assert other.teacher_user_id == immediate["classroom"].teacher_user_id
        request_id = PendingAction.query.filter_by(entitlement_id=immediate["entitlement_id"]).one().pending_action_id
        login_teacher(client, other)
        response = client.post("/api/complete-immediate-use", json={"request_id": request_id})
        assert response.status_code == 409, response.data
        assert db.session.get(PendingAction, request_id) is not None


def test_store_and_dashboard_show_the_reminder(app, client, immediate):
    classroom = immediate["classroom"]
    with app.app_context():
        enable_class_feature(class_id=classroom.class_id, feature="store")
        request_id = PendingAction.query.filter_by(entitlement_id=immediate["entitlement_id"]).one().pending_action_id
    login_teacher(client, classroom)

    store = client.get("/admin/store").get_data(as_text=True)
    assert f'data-complete-immediate="{request_id}"' in store
    assert "Immediate-use purchases to deliver" in store

    dashboard = client.get("/admin/").get_data(as_text=True)
    assert "Sit Anywhere Today" in dashboard
    assert "1 store item<" in dashboard


def test_a_verdict_relocks_the_row_inside_its_own_transaction(app, client, requested):
    """A lock the route takes does not survive FEAT entry, so the FEAT re-locks.

    Simulates the race: the route read the pending action, then a concurrent
    Return resolved it before this Accept's FEAT ran. The Accept must find
    nothing to decide rather than write a terminal event.
    """
    from app.feats.entitlement_lifecycle_feat import (
        execute_approve_redemption,
        execute_return_redemption,
    )
    from app.services import store_service
    from app.services.context_resolver import CanonicalContext
    from app.services.entitlement_read_service import latest_entitlement_grant

    classroom = requested["classroom"]
    with app.app_context():
        ctx = CanonicalContext(
            user_id=classroom.teacher_user_id, class_id=classroom.class_id,
            seat_id=classroom.teacher_seat_id, actor_role="teacher",
        )
        stale = db.session.get(PendingAction, requested["request_id"])
        entitlement = latest_entitlement_grant(requested["entitlement_id"])
        store_item = store_service.resolve_entitlement_product(entitlement)

        execute_return_redemption(
            entitlement=entitlement, pending_action=stale, ctx=ctx,
            idempotency_key=f"t:return:{requested['request_id']}",
        )
        assert db.session.get(PendingAction, requested["request_id"]) is None

        with pytest.raises(ValueError):
            execute_approve_redemption(
                entitlement=entitlement, store_item=store_item, pending_action=stale, ctx=ctx,
                idempotency_key=f"t:approve:{requested['request_id']}",
            )
        db.session.rollback()
        assert _terminal(requested["entitlement_id"]) == []
