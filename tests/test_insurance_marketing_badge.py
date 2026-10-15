"""Insurance marketing badge — optional teacher flair, ported from v1 (DOM-POL-001A §D).

Presentation only: FEAT-CLASS-003 stores a key from the fixed catalog, rejects any
other value, and the student marketplace renders the badge's label.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.extensions import db
from app.feats.class_configuration import configure_insurance_definition
from app.feats.class_configuration.feat_class_003_insurance_policy_management import (
    InsuranceContractViolation,
)
from app.services.insurance_policy_service import MARKETING_BADGES
from tests.helpers.canonical_classroom import login_student, provision_classroom
from tests.helpers.class_domain import enable_class_feature
from tests.test_insurance_purchase_feat import _submission, _teacher_ctx


def _configure(classroom, **overrides):
    return configure_insurance_definition(
        class_id=classroom.class_id,
        submission=_submission(**overrides),
        canonical_context=_teacher_ctx(classroom),
        correlation_id=f"corr_{uuid4().hex}",
        idempotency_key=f"cfg:{uuid4().hex}",
    )


def _classroom():
    classroom = provision_classroom("chemistry_p1")
    enable_class_feature(class_id=classroom.class_id, feature="insurance")
    return classroom


def test_v1_badge_catalog_is_complete():
    assert len(MARKETING_BADGES) == 16


def test_marketing_badge_stored_and_shown_to_student(app, client):
    with app.app_context():
        classroom = _classroom()
        row = _configure(classroom, marketing_badge="definitely_not_scam")
        db.session.commit()
        assert row.marketing_badge == "definitely_not_scam"
        login_student(client, classroom.students[0])

    html = client.get("/student/insurance").get_data(as_text=True)
    assert "Definitely Not a Scam" in html


def test_no_badge_by_default(app):
    with app.app_context():
        row = _configure(_classroom())
        db.session.commit()
        assert row.marketing_badge is None


def test_unknown_marketing_badge_rejected(app):
    with app.app_context():
        classroom = _classroom()
        with pytest.raises(InsuranceContractViolation, match="marketing_badge"):
            _configure(classroom, marketing_badge="free_money")


def test_teacher_sets_badge_through_form_and_edit_keeps_it(app, client):
    from app.models import InsurancePolicy
    from tests.helpers.canonical_classroom import login_teacher

    with app.app_context():
        classroom = _classroom()
        class_id = classroom.class_id
        login_teacher(client, classroom)

    assert b'id="marketing_badge"' in client.get("/admin/insurance/new").data
    resp = client.post("/admin/insurance/new", data={
        "insurance_type": "TRANSACTION", "premium": "5.00", "charge_frequency": "WEEKLY",
        "bill_preview_days": "3", "nonpayment_mode": "ACCUMULATE",
        "reimbursement_percentage": "80", "payout_multiple": "3",
        "claims_per_week_equivalent": "1", "claim_window_days": "7",
        "title": "Chaos Cover", "marketing_badge": "chaos_insurance",
    })
    assert resp.status_code == 302
    with app.app_context():
        row = InsurancePolicy.query.filter_by(class_id=class_id).one()
        assert row.marketing_badge == "chaos_insurance"
        policy_uuid = row.policy_uuid

    edit = client.get(f"/admin/insurance/edit/{policy_uuid}").get_data(as_text=True)
    assert '<option value="chaos_insurance" selected>' in edit
