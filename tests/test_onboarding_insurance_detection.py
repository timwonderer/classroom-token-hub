"""The Getting Started widget's "Set up insurance" item was hardcoded incomplete.

Every other onboarding item in admin.onboarding_status() is derived live from
whether the corresponding configuration row exists for the active class
(PayrollSettings, StoreProduct, EconomicEngine, RentSettings, HallPassSettings).
``insurance`` alone was a bare ``False`` literal -- a teacher who had actually
configured and was actively using insurance (live-tested tonight: two policies,
real claims filed and approved) still saw "Set up insurance" as an open,
un-skippable checklist item forever.
"""
from __future__ import annotations

from uuid import uuid4

from app.feats.class_configuration import configure_insurance_definition
from app.services.context_resolver import CanonicalContext
from tests.helpers.classroom_initializer import initialize_as_teacher


def _teacher_ctx(classroom):
    return CanonicalContext(
        user_id=classroom.teacher_user.id, class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id, actor_role="teacher",
    )


def _make_transaction_policy(classroom):
    configure_insurance_definition(
        class_id=classroom.class_id,
        submission=dict(
            insurance_type="TRANSACTION", premium="10.00", charge_frequency="WEEKLY", bill_preview_days=3, nonpayment_mode="ACCUMULATE",
            reimbursement_percentage="80", payout_multiple="3",
            claims_per_week_equivalent="1", claim_window_days="7",
            title="Basic Cover",
        ),
        canonical_context=_teacher_ctx(classroom),
        correlation_id=f"corr_{uuid4().hex}",
        idempotency_key=f"cfg:{uuid4().hex}",
    )


def test_insurance_reports_incomplete_with_no_policy(app, client):
    classroom = initialize_as_teacher("chemistry_p1", client, app)

    payload = client.get("/admin/onboarding/status").get_json()

    assert payload["status"] == "success"
    assert payload["completion"]["insurance"] is False


def test_insurance_reports_complete_once_a_policy_exists(app, client):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with app.app_context():
        _make_transaction_policy(classroom)

    payload = client.get("/admin/onboarding/status").get_json()

    assert payload["status"] == "success"
    assert payload["completion"]["insurance"] is True, (
        "a class with a configured insurance policy must not show "
        "'Set up insurance' as an open onboarding task"
    )
