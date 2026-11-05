"""Teacher hall-pass adjustments are independent, scoped and replay-safe."""
from decimal import Decimal

import pytest
from flask import template_rendered

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.direct_entitlement_grant_feat import execute_hall_pass_adjustment
from app.feats.store_purchase_feat import execute_store_purchase
from app.models import EntitlementEvent, Transaction
from app.services.context_resolver import CanonicalContext
from app.services.entitlement_service import get_hall_pass_balance
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher, initialize_as_student
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.ledger import record_ledger_fixture
from tests.helpers.store_products import publish_store_product


def _post(client, student, surface, key, action="add", quantity=1):
    if surface == "bulk":
        return client.post('/admin/students/bulk-adjust-hall-pass-entitlements', json={
            "student_ids": [student.seat_id], "update_type": action,
            "value": quantity, "request_id": key,
        })
    return client.post(f'/admin/student/{student.seat.public_id}/adjust-hall-pass-entitlements', data={
        "hall_pass_action": action, "hall_pass_quantity": quantity, "request_id": key,
    })


@pytest.mark.parametrize("surface", ["bulk", "detail"])
@pytest.mark.parametrize("operation", ["add", "remove"])
def test_replayed_adjustment_is_a_noop(client, app, surface, operation):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    if operation == "remove":
        _post(client, student, surface, "seed", quantity=2)
    for _ in range(2):
        response = _post(client, student, surface, "replay", operation, 1)
        assert response.status_code == (200 if surface == "bulk" else 302)
    assert get_hall_pass_balance(student.seat_id, classroom.class_id) == 1


@pytest.mark.parametrize("surface", ["bulk", "detail"])
def test_new_request_key_creates_new_grant(client, app, surface):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    for key in ("first", "second"):
        response = _post(client, student, surface, key, quantity=2)
        assert response.status_code == (200 if surface == "bulk" else 302)
    assert get_hall_pass_balance(student.seat_id, classroom.class_id) == 4


@pytest.mark.parametrize("surface", ["bulk", "detail"])
def test_adjustment_events_name_teacher_without_product(client, app, surface):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    _post(client, student, surface, "grant", quantity=2)
    _post(client, student, surface, "remove", "remove", 1)
    events = EntitlementEvent.query.filter_by(class_id=classroom.class_id, target_seat_id=student.seat_id).all()
    assert len(events) == 3
    assert all(event.actor_seat_id == classroom.teacher_seat_id for event in events)
    assert all(event.product_id is None for event in events)


@pytest.mark.parametrize("surface", ["bulk", "detail"])
@pytest.mark.parametrize("action,quantity", [("add", 3), ("remove", 2)])
def test_changed_replay_payload_is_rejected(client, app, surface, action, quantity):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    _post(client, student, surface, "first", quantity=2)
    response = _post(client, student, surface, "first", action, quantity)
    assert response.status_code == (200 if surface == "bulk" else 302)
    if surface == "bulk":
        assert response.get_json()["status"] == "error"
        assert "different inputs" in response.get_json()["errors"][0]
        assert response.get_json()["errors"][0].startswith(student.seat.identity_profile.full_name + ": ")
    else:
        with client.session_transaction() as session:
            assert any(category == "error" and "different inputs" in message for category, message in session["_flashes"])
    assert get_hall_pass_balance(student.seat_id, classroom.class_id) == 2


@pytest.mark.parametrize("surface", ["bulk", "detail"])
def test_adjustment_cannot_target_another_class(client, app, surface):
    other = initialize("ap_csp_p3", app)
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    response = _post(client, other.students[0], surface, "wrong-class")
    assert response.status_code == (200 if surface == "bulk" else 404)
    if surface == "bulk":
        assert response.get_json()["status"] == "error"
    assert get_hall_pass_balance(other.students[0].seat_id, other.class_id) == 0
    assert EntitlementEvent.query.filter_by(class_id=classroom.class_id).count() == 0


def test_student_actor_cannot_call_adjustment(app):
    classroom = initialize("chemistry_p1", app)
    student = classroom.students[0]
    ctx = CanonicalContext(user_id=student.user_id, class_id=classroom.class_id,
                           seat_id=student.seat_id, actor_role="student")
    with pytest.raises(ValueError, match="Teacher authority"):
        execute_hall_pass_adjustment(canonical_context=ctx, target_seat_id=student.seat_id,
                                    quantity=1, operation="add",
                                    idempotency_key="hall-pass:actor-check")
    assert get_hall_pass_balance(student.seat_id, classroom.class_id) == 0


def test_purchase_increases_count_and_transaction_but_not_my_items(client, app):
    classroom, student = initialize_as_student("chemistry_p1", client, app)
    enable_class_feature(class_id=classroom.class_id, feature="store")
    with FEATContext("FEAT-LED-001", idempotency_key="hall-pass:fund"):
        record_ledger_fixture(seat_id=student.seat_id, class_id=classroom.class_id, amount=Decimal("100.00"))
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="hall-pass:product"):
        product = publish_store_product(class_id=classroom.class_id, entitlement_type="HALL_PASS",
                                        name="Hall Pass", price="5.00", created_by_seat_id=classroom.teacher_seat_id)
    result = execute_store_purchase(
        canonical_context=CanonicalContext(user_id=student.user_id, class_id=classroom.class_id,
                                           seat_id=student.seat_id, actor_role="student"),
        policy_uuid=product.policy_uuid, quantity=2,
    )
    assert result.success, result.error_code
    assert get_hall_pass_balance(student.seat_id, classroom.class_id) == 2
    assert Transaction.query.filter_by(class_id=classroom.class_id, seat_id=student.seat_id, type="purchase").count() == 1
    assert EntitlementEvent.query.filter_by(class_id=classroom.class_id, target_seat_id=student.seat_id, event_type="CONSUMED").count() == 0
    rendered = []
    def capture(sender, template, context, **extra):
        if template.name == 'student_shop.html':
            rendered.append(context)
    with template_rendered.connected_to(capture, app):
        response = client.get('/student/shop')
    assert response.status_code == 200
    assert rendered and rendered[0]['entitlements'] == []
    assert rendered[0]['items'], "hall passes must remain purchasable"


@pytest.mark.parametrize("case", ["boolean", "fraction", "negative", "invalid-seat", "missing-key"])
def test_bulk_rejects_invalid_inputs_before_any_adjustment(client, app, case):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    valid = {"student_ids": [student.seat_id], "update_type": "add", "value": 1, "request_id": "validation"}
    changes = {"boolean": {"value": True}, "fraction": {"value": 1.5}, "negative": {"value": -1},
               "invalid-seat": {"student_ids": [student.seat_id, "invalid"]}, "missing-key": {"request_id": ""}}
    response = client.post('/admin/students/bulk-adjust-hall-pass-entitlements', json=valid | changes[case])
    assert response.status_code == 400
    assert get_hall_pass_balance(student.seat_id, classroom.class_id) == 0


def test_detail_form_supplies_a_new_request_id(client, app):
    from bs4 import BeautifulSoup
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    roster = client.get('/admin/students')
    assert roster.status_code == 200
    links = BeautifulSoup(roster.data, 'html.parser').find_all('a', href=True)
    detail_url = next(link['href'] for link in links if f'/admin/students/{student.seat.public_id}?' in link['href'])
    _post(client, student, "detail", "detail-purchase-view")
    rendered = []
    def capture(sender, template, context, **extra):
        if template.name == 'student_detail.html':
            rendered.append(context)
    tokens = []
    for _ in range(2):
        with template_rendered.connected_to(capture, app):
            response = client.get(detail_url)
        assert response.status_code == 200
        form = BeautifulSoup(response.data, 'html.parser').find('form', action=f'/admin/student/{student.seat.public_id}/adjust-hall-pass-entitlements')
        assert form.find('input', {'name': 'csrf_token'})
        tokens.append(form.find('input', {'name': 'request_id'})['value'])
    assert tokens[0] and tokens[0] != tokens[1]
    assert rendered and rendered[0]["entitlements"] == []


@pytest.mark.parametrize("surface", ["bulk", "detail"])
def test_long_request_id_grant_can_be_used(client, app, surface):
    from app.feats.prod import record_hall_pass_log
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    response = _post(client, student, surface, "x" * 128)
    assert response.status_code == (200 if surface == "bulk" else 302)
    grant = EntitlementEvent.query.filter_by(
        class_id=classroom.class_id, target_seat_id=student.seat_id, event_type="GRANTED",
    ).one()
    assert len(grant.correlation_id) <= 100
    result = record_hall_pass_log(
        ctx=CanonicalContext(user_id=classroom.teacher_user_id, class_id=classroom.class_id,
                             seat_id=classroom.teacher_seat_id, actor_role="teacher"),
        requested_by_seat_id=student.seat_id, approved_by_seat_id=classroom.teacher_seat_id,
        destination="Bathroom", reason="teacher_approved", idempotency_key="hall-pass:use-long-key",
    )
    assert result.hall_pass_log.correlation_id == grant.correlation_id
    assert get_hall_pass_balance(student.seat_id, classroom.class_id) == 0


def test_hall_pass_history_does_not_hide_older_my_items(client, app):
    from app.services.entitlement_service import grant_hall_passes
    classroom, student = initialize_as_student("chemistry_p1", client, app)
    enable_class_feature(class_id=classroom.class_id, feature="store")
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="history:product"):
        product = publish_store_product(class_id=classroom.class_id, entitlement_type="DELAYED_USE",
                                        name="Homework Pass", price="0.00", created_by_seat_id=classroom.teacher_seat_id)
    result = execute_store_purchase(
        canonical_context=CanonicalContext(user_id=student.user_id, class_id=classroom.class_id,
                                           seat_id=student.seat_id, actor_role="student"),
        policy_uuid=product.policy_uuid, quantity=1,
    )
    assert result.success, result.error_code
    with FEATContext("FEAT-TEST-SETUP", idempotency_key="history:passes"):
        grant_hall_passes(student.seat, 101, actor_seat_id=classroom.teacher_seat_id)
    rendered = []
    def capture(sender, template, context, **extra):
        if template.name == 'student_shop.html':
            rendered.append(context)
    with template_rendered.connected_to(capture, app):
        response = client.get('/student/shop')
    assert response.status_code == 200
    assert rendered and len(rendered[0]['entitlements']) == 1


@pytest.mark.parametrize("surface", ["bulk", "detail"])
def test_adjustment_quantity_limit_is_per_request(client, app, surface):
    """Accept 100, reject 101 for both actions, and allow a balance above 100."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    _post(client, student, surface, "cap-seed", quantity=100)
    assert get_hall_pass_balance(student.seat_id, classroom.class_id) == 100
    for operation in ("add", "remove"):
        response = _post(client, student, surface, f"cap-reject-{operation}", operation, 101)
        if surface == "bulk":
            assert response.get_json()["status"] == "error"
            assert "between 1 and 100" in response.get_json()["errors"][0]
        else:
            with client.session_transaction() as session:
                assert any(category == "error" and "between 1 and 100" in message
                           for category, message in session["_flashes"])
        assert get_hall_pass_balance(student.seat_id, classroom.class_id) == 100
    _post(client, student, surface, "cap-next-request", quantity=1)
    assert get_hall_pass_balance(student.seat_id, classroom.class_id) == 101
    _post(client, student, surface, "cap-remove", "remove", 100)
    assert get_hall_pass_balance(student.seat_id, classroom.class_id) == 1
