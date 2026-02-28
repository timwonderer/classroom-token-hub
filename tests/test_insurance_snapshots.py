from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app import db
from app.models import Admin, InsurancePolicy, InsuranceClaim, StudentInsurance, StudentTeacher, Transaction, TransactionStatus


def _create_policy(admin_id: int, *, title: str = "Snapshot Coverage", max_claim_amount=Decimal("75.00")):
    policy = InsurancePolicy(
        policy_code=f"POL-{title[:3].upper()}-{admin_id}",
        teacher_id=admin_id,
        title=title,
        description="Base policy",
        premium=Decimal("10.00"),
        claim_type="transaction_monetary",
        is_monetary=True,
        max_claim_amount=max_claim_amount,
        max_claims_period="month",
        claim_time_limit_days=30,
        is_active=True,
    )
    db.session.add(policy)
    db.session.commit()
    return policy


def test_insurance_policy_version_increments_on_edit(client):
    admin = Admin(username="policy-version-admin", totp_secret="secret")
    db.session.add(admin)
    db.session.commit()

    policy = _create_policy(admin.id)
    assert policy.version_number == 1

    policy.title = "Snapshot Coverage Updated"
    db.session.commit()

    db.session.refresh(policy)
    assert policy.version_number == 2


def test_student_insurance_keeps_frozen_snapshot_after_policy_edit(client, test_student):
    admin = Admin(username="snapshot-admin", totp_secret="secret")
    db.session.add(admin)
    db.session.commit()

    policy = _create_policy(admin.id, title="Original Policy", max_claim_amount=Decimal("42.00"))

    enrollment = StudentInsurance(
        student_id=test_student.id,
        policy_id=policy.id,
        status="active",
        purchase_date=datetime.now(timezone.utc),
        coverage_start_date=datetime.now(timezone.utc) - timedelta(days=1),
        payment_current=True,
    )
    enrollment.freeze_policy_snapshot(policy)
    db.session.add(enrollment)
    db.session.commit()

    policy.title = "Mutated Template Title"
    policy.description = "Mutated template description"
    policy.max_claim_amount = Decimal("999.00")
    policy.max_claims_count = 99
    policy.claim_time_limit_days = 5
    db.session.commit()

    db.session.refresh(enrollment)

    assert enrollment.contract_title == "Original Policy"
    assert enrollment.contract_description == "Base policy"
    assert enrollment.contract_max_claim_amount == Decimal("42.00")
    assert enrollment.contract_claim_time_limit_days == 30
    assert enrollment.policy_version == 1


def test_admin_claim_approval_uses_frozen_claim_cap(client, test_student):
    admin = Admin(username="snapshot-claim-admin", totp_secret="secret")
    db.session.add(admin)
    db.session.flush()

    db.session.add(StudentTeacher(student_id=test_student.id, admin_id=admin.id))
    db.session.commit()

    policy = _create_policy(admin.id, title="Claim Cap Policy", max_claim_amount=Decimal("100.00"))

    enrollment = StudentInsurance(
        student_id=test_student.id,
        policy_id=policy.id,
        status="active",
        join_code="JOIN-SNAP-1",
        purchase_date=datetime.now(timezone.utc),
        coverage_start_date=datetime.now(timezone.utc) - timedelta(days=2),
        payment_current=True,
    )
    enrollment.freeze_policy_snapshot(policy)
    enrollment.frozen_max_claim_amount = Decimal("20.00")
    db.session.add(enrollment)
    db.session.flush()

    tx = Transaction(
        student_id=test_student.id,
        teacher_id=admin.id,
        join_code="JOIN-SNAP-1",
        amount=Decimal("-50.00"),
        account_type="checking",
        status=TransactionStatus.POSTED,
        type="purchase",
        description="Purchase: Lost calculator",
    )
    db.session.add(tx)
    db.session.flush()

    claim = InsuranceClaim(
        student_insurance_id=enrollment.id,
        policy_id=policy.id,
        student_id=test_student.id,
        incident_date=tx.timestamp,
        description="Need reimbursement",
        claim_amount=Decimal("50.00"),
        status="pending",
        transaction_id=tx.id,
    )
    db.session.add(claim)
    db.session.commit()

    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = admin.id
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()

    client.post(
        f"/admin/insurance/claim/{claim.id}",
        data={
            "status": "approved",
            "approved_amount": "",
            "rejection_reason": "",
            "admin_notes": "",
        },
        follow_redirects=True,
    )

    db.session.refresh(claim)
    assert claim.status == "approved"
    assert claim.approved_amount == Decimal("20.00")

    reimbursement = Transaction.query.filter(
        Transaction.type == "insurance_reimbursement",
        Transaction.original_transaction_id == tx.id,
        Transaction.policy_id == policy.id,
    ).first()
    assert reimbursement is not None
    assert reimbursement.amount == Decimal("20.00")
