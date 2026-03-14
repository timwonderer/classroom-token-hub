from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import Admin, InsurancePolicy


def test_insurance_policy_product_type_and_tier_fallbacks():
    policy = InsurancePolicy(
        policy_code="POL-MOD-1",
        teacher_id=1,
        title="Fallback Policy",
        premium=Decimal("10.00"),
        claim_type="legacy_monetary",
        tier_category_id=123,
        tier_level="premium",
    )

    assert policy.product_type == "custom_monetary"
    assert policy.effective_product_group_id == 123
    assert policy.effective_tier_rank == 3
    assert policy.effective_coverage_percent is None


def test_normalized_tier_uniqueness_enforced(client):
    admin = Admin(username="tier-unique-admin", totp_secret="secret")
    db.session.add(admin)
    db.session.flush()

    one = InsurancePolicy(
        policy_code="POL-GRP-1",
        teacher_id=admin.id,
        title="Basic Plan",
        premium=Decimal("5.00"),
        claim_type="transaction_monetary",
        coverage_percent=Decimal("0.5"),
        product_group_id=42,
        tier_rank=1,
    )
    two = InsurancePolicy(
        policy_code="POL-GRP-2",
        teacher_id=admin.id,
        title="Duplicate Basic",
        premium=Decimal("6.00"),
        claim_type="transaction_monetary",
        coverage_percent=Decimal("0.6"),
        product_group_id=42,
        tier_rank=1,
    )
    db.session.add(one)
    db.session.commit()

    db.session.add(two)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
