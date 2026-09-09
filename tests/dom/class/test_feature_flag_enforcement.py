"""
Test that feature flags properly block access to disabled features.

This ensures that when a teacher disables a feature (banking, payroll, etc.),
students cannot access those routes even via direct URL.
"""

import pytest

from app.extensions import db
from app.models import ClassFeature, StoreProduct
from app.services.store_service import IN_USE
from tests.helpers.store_products import publish_store_product
from app.feats.base import FEATContext
from tests.helpers.class_domain import disable_class_feature, enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_student, initialize_as_teacher
from tests.helpers.ledger import create_ledger_idempotent_transaction

from decimal import Decimal

from app.services.ledger_balance_query_service import get_available_balances

# tests/helpers/canonical_identities.py provisions every student with this PIN.
CANONICAL_STUDENT_PIN = "1234"

pytestmark = [pytest.mark.critical, pytest.mark.regression]


@pytest.fixture
def setup_student_with_disabled_banking(client):
    """Create a student with banking feature disabled."""
    classroom, student = initialize_as_student("chemistry_p1", client, client.application)
    teacher = classroom.teacher_user
    user = student.user
    student_seat = student.seat
    with FEATContext("FEAT-LED-001", idempotency_key="feature_flag_enforcement:disabled_banking:seed"):
        create_ledger_idempotent_transaction(
            idempotency_key="feature_flag_enforcement:disabled_banking:seed",
            seat_id=student_seat.id,
            class_id=classroom.class_id,
            user_id=user.id,
            amount="100.00",
            account_type="checking",
            type="purchase",
            description="Starting balance",
            actor_seat_id=student_seat.id,
        )
    disable_class_feature(class_id=classroom.class_id, feature='banking')
    db.session.commit()

    return {
        'teacher': teacher,
        'join_code': classroom.join_code,
        'class_id': classroom.class_id,
        'seat_id': student_seat.id,
        'user_id': user.id,
        'period': 'Period2',
    }


@pytest.fixture
def setup_student_with_enabled_banking(client):
    """Create a student with banking feature enabled."""
    classroom, student = initialize_as_student("ap_csp_p3", client, client.application)
    teacher = classroom.teacher_user
    student_seat = student.seat
    user = student.user
    with FEATContext("FEAT-LED-001", idempotency_key="feature_flag_enforcement:enabled_banking:seed"):
        create_ledger_idempotent_transaction(
            idempotency_key="feature_flag_enforcement:enabled_banking:seed",
            seat_id=student_seat.id,
            class_id=classroom.class_id,
            user_id=user.id,
            amount="100.00",
            account_type="checking",
            type="purchase",
            description="Starting balance",
            actor_seat_id=student_seat.id,
        )
    enable_class_feature(class_id=classroom.class_id, feature='banking')
    db.session.commit()

    return {
        'teacher': teacher,
        'join_code': classroom.join_code,
        'class_id': classroom.class_id,
        'seat_id': student_seat.id,
        'user_id': user.id,
        'period': 'Period1',
    }


def test_DOM_CLASS_001__transfer_allowed_when_banking_enabled(client, setup_student_with_enabled_banking):
    """Test that transfer routes are not blocked by the feature flag when enabled.

    The handler reads `pin`, per the FEAT-IDEN-002 credential boundary. This test
    used to submit `passphrase` and accept either redirect target, so it passed
    whether the transfer succeeded or was rejected — it proved only that the
    feature flag did not abort the request.
    """
    data = setup_student_with_enabled_banking

    response = client.get('/student/transfer', follow_redirects=False)
    assert response.status_code == 200
    assert b'Transfer Details' in response.data or b'Finances' in response.data

    # The GET mints the single-use transfer token, so it has to be read back
    # from the session rather than planted beforehand — a planted value is
    # overwritten by the GET and the POST is then refused as a replay.
    with client.session_transaction() as sess:
        transfer_token = sess['transfer_token']

    response = client.post('/student/transfer', data={
        'from_account': 'checking',
        'to_account': 'savings',
        'amount': '50.00',
        'pin': CANONICAL_STUDENT_PIN,
        'transfer_token': transfer_token,
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Incorrect PIN' not in response.data
    checking, savings = get_available_balances(data['seat_id'], data['class_id'])
    assert checking == Decimal('50.00')
    assert savings == Decimal('50.00')


def test_DOM_CLASS_001__transfer_rejected_with_wrong_pin(client, setup_student_with_enabled_banking):
    """An incorrect PIN must leave both balances untouched."""
    data = setup_student_with_enabled_banking

    assert client.get('/student/transfer').status_code == 200
    with client.session_transaction() as sess:
        transfer_token = sess['transfer_token']

    response = client.post('/student/transfer', data={
        'from_account': 'checking',
        'to_account': 'savings',
        'amount': '50.00',
        'pin': '9999',
        'transfer_token': transfer_token,
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Incorrect PIN' in response.data
    checking, savings = get_available_balances(data['seat_id'], data['class_id'])
    assert checking == Decimal('100.00')
    assert savings == Decimal('0.00')


def test_DOM_CLASS_001__payroll_allowed_when_payroll_enabled(client, setup_student_with_enabled_banking):
    """Test that payroll works normally when payroll is enabled."""
    _ = setup_student_with_enabled_banking

    response = client.get('/student/payroll', follow_redirects=False)
    assert response.status_code == 200
    assert b'Payroll' in response.data or b'payroll' in response.data


def test_DOM_CLASS_001__admin_banking_enabled_renders_without_enforcement_header(client):
    """ENABLED state: banking is default-enabled, so the guard must NOT intercept.

    The route renders normally (200) and emits NEITHER enforcement header. This
    is the positive control that proves the guard fails *open* only when scope is
    resolved AND enabled -- never on an unresolved/None scope.
    """
    initialize_as_teacher("chemistry_p1", client, client.application)

    response = client.get('/admin/banking')
    assert response.status_code == 200
    assert response.headers.get("X-Feature-Disabled") is None
    assert response.headers.get("X-Feature-Unresolved") is None


def test_DOM_CLASS_001__admin_banking_rejects_disabled_class_scope(client):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    disable_class_feature(class_id=classroom.class_id, feature='banking')
    db.session.commit()

    response = client.get('/admin/banking')
    assert response.status_code == 200
    # Assert on the stable, machine-readable capability signal rather than page
    # copy: the guard emits X-Feature-Disabled=<feature> for the DISABLED state.
    assert response.headers.get("X-Feature-Disabled") == "banking"


def test_DOM_CLASS_001__capability_state_unresolved_fails_closed(client):
    """UNRESOLVED state: a None/absent class scope is a failure to establish
    authority, and MUST fail closed (404) rather than render the feature.

    This asserts the authorization *default* directly at the shared capability
    boundary: when no lawful class scope exists, ``_resolve_feature_capability_state``
    returns UNRESOLVED and the guard's unresolved response is a headered 404. The
    old ``if scope and not scope["enabled"]`` pattern was backwards precisely here
    -- it let None (no authority) fall through into the feature.
    """
    from flask import g
    from app.routes import admin as admin_module

    with client.application.test_request_context('/admin/banking'):
        g.admin_class_context = None
        assert (
            admin_module._resolve_feature_capability_state('banking')
            == admin_module.FEATURE_CAPABILITY_UNRESOLVED
        )

        response = admin_module._feature_unresolved_response('banking')
        assert response.status_code == 404
        assert response.headers.get("X-Feature-Unresolved") == "banking"


def test_DOM_CLASS_001__admin_store_rejects_disabled_class_scope(client):
    classroom_b = initialize_as_teacher("ap_csp_p3", client, client.application)
    disable_class_feature(class_id=classroom_b.class_id, feature='store')
    db.session.commit()

    response = client.get('/admin/store')
    assert response.status_code == 200
    assert response.headers.get("X-Feature-Disabled") == "store"


def test_DOM_CLASS_001__admin_hall_pass_rejects_disabled_class_scope(client):
    classroom_b = initialize_as_teacher("ap_csp_p3", client, client.application)
    disable_class_feature(class_id=classroom_b.class_id, feature='hall_pass')
    db.session.commit()

    response = client.get('/admin/hall-pass')
    assert response.status_code == 200
    assert response.headers.get("X-Feature-Disabled") == "hall_pass"


def test_DOM_CLASS_001__admin_payroll_rejects_disabled_class_scope(client):
    classroom_b = initialize_as_teacher("ap_csp_p3", client, client.application)
    disable_class_feature(class_id=classroom_b.class_id, feature='payroll')
    db.session.commit()

    response = client.get('/admin/payroll')
    assert response.status_code == 200
    assert response.headers.get("X-Feature-Disabled") == "payroll"


def test_DOM_CLASS_001__admin_store_delete_rejects_disabled_class_scope(client):
    """A disabled store closes the whole surface, deletion included.

    The scope gate runs before the route resolves the product, so a class with
    the store turned off cannot reach its own catalog even to destroy it.
    """
    classroom_b = initialize_as_teacher("ap_csp_p3", client, client.application)
    disable_class_feature(class_id=classroom_b.class_id, feature='store')
    db.session.commit()
    with FEATContext("FEAT-SETTINGS-001", idempotency_key=f"feature_flag_enforcement:store_item:{classroom_b.class_id}"):
        product = publish_store_product(
            class_id=classroom_b.class_id,
            entitlement_type="IMMEDIATE_USE",
            user_id=classroom_b.teacher_user.id,
            name="Pencil",
            description="Simple item",
            price="1.00",
        )
    response = client.post(
        f'/admin/store/hard-delete/{product.product_lineage_uuid}',
        data={'join_code': 'STD2'},
        follow_redirects=False,
    )
    assert response.status_code == 404
    survivor = db.session.query(StoreProduct).filter_by(policy_uuid=product.policy_uuid).one()
    assert survivor.availability_state == IN_USE


def test_DOM_CLASS_001__student_rent_rejects_disabled_class_scope(client):
    classroom, student = initialize_as_student("chemistry_p1", client, client.application)
    disable_class_feature(class_id=classroom.class_id, feature='rent')
    db.session.commit()

    response = client.get('/student/rent', follow_redirects=False)
    assert response.status_code == 404
