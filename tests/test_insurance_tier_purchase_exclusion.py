"""Tier-group mutual exclusion at purchase (FEAT-CLASS-003 §VIII.3, FEAT-OBL-004).

A seat may hold at most one active insurance coverage per tier_group: buying a
second tier of a group it already holds fails POLICY_ALREADY_HELD_IN_GROUP.
Different groups and ungrouped policies are unaffected.
"""

from __future__ import annotations

from uuid import uuid4

from app.extensions import db
from app.feats.purchase_insurance_feat import execute_purchase_insurance
from app.feats.class_configuration import configure_insurance_definition
from tests.test_insurance_purchase_feat import _teacher_ctx, _student_ctx, _submission, _fund
from tests.helpers.classroom_initializer import initialize
from tests.helpers.class_domain import enable_class_feature


def _tier(classroom, group, level):
    from tests.helpers.insurance_domain import provision_tier_group
    group_id = provision_tier_group(classroom.class_id, group)
    row = configure_insurance_definition(
        class_id=classroom.class_id,
        submission=_submission(tier_group_id=group_id, tier_level=level),
        canonical_context=_teacher_ctx(classroom),
        correlation_id=f"corr_{uuid4().hex}",
        idempotency_key=f"cfg:{uuid4().hex}",
    )
    return row.policy_uuid


def _single(classroom):
    row = configure_insurance_definition(
        class_id=classroom.class_id,
        submission=_submission(),
        canonical_context=_teacher_ctx(classroom),
        correlation_id=f"corr_{uuid4().hex}",
        idempotency_key=f"cfg:{uuid4().hex}",
    )
    return row.policy_uuid


def _buy(classroom, policy_uuid, idem):
    r = execute_purchase_insurance(
        canonical_context=_student_ctx(classroom),
        policy_uuid=policy_uuid, idempotency_key=idem,
    )
    db.session.commit()
    return r


def _setup(app):
    classroom = initialize("chemistry_p1", app)
    enable_class_feature(class_id=classroom.class_id, feature="insurance")
    _fund(classroom.students[0].seat, "100.00")
    return classroom


def test_second_tier_same_group_rejected(app):
    classroom = _setup(app)
    with app.app_context():
        basic = _tier(classroom, "Paycheck Protection", 1)
        mid = _tier(classroom, "Paycheck Protection", 2)
        db.session.commit()

        assert _buy(classroom, basic, "b1").success
        r = _buy(classroom, mid, "m1")
        assert r.success is False
        assert r.error_code == "POLICY_ALREADY_HELD_IN_GROUP"


def test_coverage_in_a_different_group_allowed(app):
    classroom = _setup(app)
    with app.app_context():
        pay_basic = _tier(classroom, "Paycheck Protection", 1)
        dev_basic = _tier(classroom, "Device Insurance", 1)
        db.session.commit()

        assert _buy(classroom, pay_basic, "b1").success
        assert _buy(classroom, dev_basic, "d1").success  # different group — fine


def test_ungrouped_policies_not_group_excluded(app):
    classroom = _setup(app)
    with app.app_context():
        p1 = _single(classroom)
        p2 = _single(classroom)
        db.session.commit()

        assert _buy(classroom, p1, "s1").success
        # A different ungrouped policy is not blocked by group exclusion.
        assert _buy(classroom, p2, "s2").success


def test_tier_description_shown_before_purchase(app, client):
    """A tiered plan's teacher description is readable in the Buy tab and the buy
    confirmation — terms must not first appear after purchase."""
    from tests.helpers.canonical_classroom import provision_classroom, login_student

    terms = "Covers up to two absences per week, eight per month."
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        enable_class_feature(class_id=classroom.class_id, feature="insurance")
        row = configure_insurance_definition(
            class_id=classroom.class_id,
            submission=_submission(tier_group="Paycheck Protection", tier_level=1, description=terms),
            canonical_context=_teacher_ctx(classroom),
            correlation_id=f"corr_{uuid4().hex}",
            idempotency_key=f"cfg:{uuid4().hex}",
        )
        db.session.commit()
        policy_uuid = row.policy_uuid
        login_student(client, classroom.students[0])

    resp = client.get("/student/insurance")
    html = resp.get_data(as_text=True)
    modal = html[html.index(f'id="buy-{policy_uuid}"'):]
    assert html.count(terms) >= 2  # tier row + buy modal
    assert terms in modal[: modal.index("</form>")]


def test_successor_identity_excludes_coverage_but_independent_same_label_does_not(app):
    classroom = _setup(app)
    original = _tier(classroom, "Coverage", 1)
    assert _buy(classroom, original, "continuity:original").success
    successor = configure_insurance_definition(class_id=classroom.class_id,
        submission=_submission(tier_group="Coverage", tier_level=1),
        canonical_context=_teacher_ctx(classroom), supersedes_policy_uuid=original,
        idempotency_key=f"successor:{uuid4()}")
    assert not _buy(classroom, successor.policy_uuid, "continuity:successor").success
    independent = configure_insurance_definition(class_id=classroom.class_id,
        submission=_submission(tier_group="Coverage", tier_level=1),
        canonical_context=_teacher_ctx(classroom), idempotency_key=f"independent:{uuid4()}")
    assert independent.tier_group_id != successor.tier_group_id
    assert _buy(classroom, independent.policy_uuid, "continuity:independent").success


def test_edit_keeps_sibling_exclusion_and_rejects_group_move(app):
    import pytest
    from app.models import InsurancePolicy
    from app.services.insurance_configuration import InsuranceContractViolation
    from tests.helpers.insurance_domain import provision_tier_group
    classroom = _setup(app)
    basic = _tier(classroom, "Coverage", 1)
    mid = _tier(classroom, "Coverage", 2)
    group_id = db.session.get(InsurancePolicy, mid).tier_group_id
    assert _buy(classroom, basic, "sibling:held").success
    successor = configure_insurance_definition(class_id=classroom.class_id,
        submission=_submission(tier_group="Coverage", tier_level=2),
        canonical_context=_teacher_ctx(classroom), supersedes_policy_uuid=mid,
        idempotency_key=f"sibling:edit:{uuid4()}")
    assert successor.tier_group_id == group_id
    assert _buy(classroom, successor.policy_uuid, "sibling:denied").error_code == "POLICY_ALREADY_HELD_IN_GROUP"
    other = provision_tier_group(classroom.class_id, "Independent")
    with pytest.raises(InsuranceContractViolation, match="preserve"):
        configure_insurance_definition(class_id=classroom.class_id,
            submission=_submission(tier_group_id=other, tier_level=2),
            canonical_context=_teacher_ctx(classroom), supersedes_policy_uuid=successor.policy_uuid,
            idempotency_key=f"sibling:move:{uuid4()}")
