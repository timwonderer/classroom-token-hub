"""The claim-review route must not report success when the domain layer refused.

Regression: ``admin.process_claim`` called ``resolve_insurance_claim(...)`` and
then unconditionally flashed "Claim approved."/"Claim rejected." and redirected,
without checking the returned result. Any legitimate domain refusal (already
decided, allowance exhausted, filing-window override missing, etc.) left the
claim's real status untouched while the teacher was told it worked -- observed
live 2026-09-21: a teacher approved a claim, the approval silently failed, and
the claim came back as "Pending" on a later visit.

Reproduced here via the simplest refusal to trigger: approving an
already-terminal claim (``ALREADY_DECIDED``). No back-dated data needed --
``TestFilingWindowApprovalGate`` in test_insurance_transaction_economics.py
covers the filing-window-specific refusal at the FEAT layer directly.

Every ORM object this module touches is created, used, and discarded within a
single ``app.app_context()`` block -- Flask-SQLAlchemy's scoped session is torn
down at context exit, so an object handed across a context boundary comes back
detached. Only primitive ids (``class_id``, ``seat_id``, ``user_id``) survive
the boundary; each new context re-derives what it needs from those.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.class_configuration import configure_insurance_definition
from app.feats.purchase_insurance_feat import execute_purchase_insurance
from app.models import InsuranceClaim
from app.services.context_resolver import CanonicalContext
from app.utils.transaction_idempotency import create_idempotent_transaction
from tests.helpers.canonical_classroom import provision_classroom
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.class_domain import enable_class_feature


def _login_by_ids(client, *, user_id, class_id, seat_id, role):
    with client.session_transaction() as sess:
        set_canonical_context(
            sess, user_id=user_id, class_id=class_id, seat_id=seat_id, role=role,
        )
        sess["role"] = "admin" if role == "teacher" else "student"


def _make_policy(*, class_id, teacher_user_id, teacher_seat_id, premium="10.00"):
    row = configure_insurance_definition(
        class_id=class_id,
        submission=dict(
            insurance_type="TRANSACTION", premium=premium, charge_frequency="WEEKLY", bill_preview_days=3, nonpayment_mode="ACCUMULATE",
            reimbursement_percentage="80", payout_multiple="3",
            claims_per_week_equivalent="5", claim_window_days="7",
            title="Basic Cover",
        ),
        canonical_context=CanonicalContext(
            user_id=teacher_user_id, class_id=class_id,
            seat_id=teacher_seat_id, actor_role="teacher",
        ),
        correlation_id=f"corr_{uuid4().hex}",
        idempotency_key=f"cfg:{uuid4().hex}",
    )
    return row.policy_uuid


def _fund(*, seat_id, class_id, amount="100.00"):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"fund:{seat_id}:{uuid4().hex}"):
        create_idempotent_transaction(
            idempotency_key=f"fund:{seat_id}:{uuid4().hex}",
            seat_id=seat_id, class_id=class_id, target_seat_id=seat_id,
            actor_seat_id=seat_id, mechanism="self",
            amount=Decimal(amount), account_type="checking", type="payroll",
            description="test funding",
        )
    db.session.commit()


def _make_claimable_txn(*, seat_id, class_id):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"txn:{seat_id}:{uuid4().hex}"):
        t, _created = create_idempotent_transaction(
            idempotency_key=f"claimtxn:{seat_id}:{uuid4().hex}",
            seat_id=seat_id, class_id=class_id, target_seat_id=seat_id,
            actor_seat_id=seat_id, mechanism="self",
            amount=Decimal("-20.00"), account_type="checking", type="purchase",
            description="Store purchase")
    db.session.commit()
    return t.id


def _provision(app):
    """One classroom, one TRANSACTION policy, ids only -- see module docstring."""
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        class_id = classroom.class_id
        teacher_user_id = classroom.teacher_user.id
        teacher_seat_id = classroom.teacher_seat.id
        student_user_id = classroom.students[0].user.id
        student_seat_id = classroom.students[0].seat.id

        enable_class_feature(class_id=class_id, feature="insurance")
        policy_uuid = _make_policy(
            class_id=class_id, teacher_user_id=teacher_user_id,
            teacher_seat_id=teacher_seat_id,
        )
    return dict(
        class_id=class_id,
        teacher_user_id=teacher_user_id,
        teacher_seat_id=teacher_seat_id,
        student_user_id=student_user_id,
        student_seat_id=student_seat_id,
        policy_uuid=policy_uuid,
    )


def _submit_claim(app, client, ids):
    with app.app_context():
        _fund(seat_id=ids["student_seat_id"], class_id=ids["class_id"])
        execute_purchase_insurance(
            canonical_context=CanonicalContext(
                user_id=ids["student_user_id"], class_id=ids["class_id"],
                seat_id=ids["student_seat_id"], actor_role="student",
            ),
            policy_uuid=ids["policy_uuid"], idempotency_key=f"ins:{uuid4().hex}",
        )
        db.session.commit()
        txn_id = _make_claimable_txn(
            seat_id=ids["student_seat_id"], class_id=ids["class_id"]
        )
        _login_by_ids(
            client, user_id=ids["student_user_id"], class_id=ids["class_id"],
            seat_id=ids["student_seat_id"], role="student",
        )

    client.post(
        f"/student/insurance/claim/{ids['policy_uuid']}",
        data={"transaction_id": str(txn_id)},
    )

    with app.app_context():
        claim = (
            InsuranceClaim.query
            .filter_by(class_id=ids["class_id"], target_seat_id=ids["student_seat_id"])
            .order_by(InsuranceClaim.submitted_at.desc())
            .first()
        )
        return claim.claim_id


def _claim_status(app, claim_id):
    with app.app_context():
        return InsuranceClaim.query.filter_by(claim_id=claim_id).one().status


def test_approving_an_already_decided_claim_does_not_flash_false_success(app, client):
    ids = _provision(app)
    claim_id = _submit_claim(app, client, ids)

    with app.app_context():
        _login_by_ids(
            client, user_id=ids["teacher_user_id"], class_id=ids["class_id"],
            seat_id=ids["teacher_seat_id"], role="teacher",
        )

    # follow_redirects=True: the flashed message must be CONSUMED by the redirect
    # target's render, exactly as a real browser would -- otherwise it leaks into
    # the next response's flash queue and produces a false positive below.
    first = client.post(
        f"/admin/insurance/claim/{claim_id}",
        data={"status": "approved"},
        follow_redirects=True,
    )
    assert first.status_code == 200
    assert b"Claim approved." in first.data
    assert _claim_status(app, claim_id) == "APPROVED"

    # Second approval attempt on an already-terminal claim must be refused, not
    # silently reported as success while leaving the claim (correctly) untouched.
    second = client.post(
        f"/admin/insurance/claim/{claim_id}",
        data={"status": "approved"},
        follow_redirects=True,
    )
    assert second.status_code == 200
    assert b"already terminal" in second.data or b"could not be approved" in second.data
    assert b"Claim approved." not in second.data, (
        "the route must not flash a success message for a refused decision"
    )
    assert _claim_status(app, claim_id) == "APPROVED", (
        "the already-terminal status must be unchanged"
    )


def test_approving_a_claim_that_succeeds_still_flashes_real_success(app, client):
    ids = _provision(app)
    claim_id = _submit_claim(app, client, ids)

    with app.app_context():
        _login_by_ids(
            client, user_id=ids["teacher_user_id"], class_id=ids["class_id"],
            seat_id=ids["teacher_seat_id"], role="teacher",
        )

    resp = client.post(
        f"/admin/insurance/claim/{claim_id}",
        data={"status": "approved"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Claim approved." in resp.data
    assert _claim_status(app, claim_id) == "APPROVED"


def _login_teacher(app, client, ids):
    with app.app_context():
        _login_by_ids(
            client, user_id=ids["teacher_user_id"], class_id=ids["class_id"],
            seat_id=ids["teacher_seat_id"], role="teacher",
        )


def test_review_page_shows_the_purchase_being_claimed_before_approval(app, client):
    """Live test 2026-09-26: the page showed the payout record (set only after
    approval) as the "linked transaction", so a teacher reviewing a pending
    purchase claim never saw the purchase."""
    ids = _provision(app)
    claim_id = _submit_claim(app, client, ids)
    _login_teacher(app, client, ids)

    html = client.get(f"/admin/insurance/claim/{claim_id}").get_data(as_text=True)

    assert "Store purchase" in html
    assert "$20.00" in html
    assert "Payout if approved as claimed" in html and "$16.00" in html  # 80% of $20
    assert "[CUSTOM]" not in html and "[TXN]" not in html


def test_rejecting_without_a_reason_is_refused(app, client):
    ids = _provision(app)
    claim_id = _submit_claim(app, client, ids)
    _login_teacher(app, client, ids)

    resp = client.post(f"/admin/insurance/claim/{claim_id}", data={"status": "rejected"}, follow_redirects=True)

    assert b"Give the student a reason" in resp.data
    assert _claim_status(app, claim_id) == "SUBMITTED"


def test_lost_time_claim_shows_each_day_and_approves_fewer_hours_with_a_note(app, client):
    """Live test 2026-09-26: a lost-time claim's review page showed neither the
    hours nor the student's explanation, and offered no way to adjust hours."""
    from datetime import datetime, timezone

    from app.feats.insurance_claim_feat import submit_insurance_claim
    from app.services import insurance_claim_service
    from app.utils.canonical_temporal_resolver import CLASS_LEVEL_EVALUATION, canonical_temporal_resolver
    from tests.test_insurance_claim_feat import _make_economic_engine_ready

    ids = _provision(app)
    with app.app_context():
        teacher_ctx = CanonicalContext(
            user_id=ids["teacher_user_id"], class_id=ids["class_id"],
            seat_id=ids["teacher_seat_id"], actor_role="teacher",
        )
        student_ctx = CanonicalContext(
            user_id=ids["student_user_id"], class_id=ids["class_id"],
            seat_id=ids["student_seat_id"], actor_role="student",
        )
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"engine:{uuid4().hex}"):
            _make_economic_engine_ready(ids["class_id"])
        # A lost-time payout is posted through payroll, which needs an active version.
        from app.models import PolicyVersion
        from app.utils.canonical_temporal_resolver import utc_now
        with FEATContext("FEAT-BYPASS-LEGACY", correlation_id=f"seed-payroll:{uuid4().hex}"):
            db.session.add(PolicyVersion(class_id=ids["class_id"], domain="payroll", version_number=1,
                                         policy_payload_json="{}", activated_at=utc_now(), is_active=True))
            db.session.flush()
        db.session.commit()
        policy_uuid = configure_insurance_definition(
            class_id=ids["class_id"],
            submission=dict(
                insurance_type="PRODUCTIVITY", premium="10.00", charge_frequency="WEEKLY",
                bill_preview_days=3, nonpayment_mode="ACCUMULATE", reimbursement_percentage="60",
                payout_multiple="5", claimable_dates_per_week_equivalent="3", title="Lost Time Cover",
            ),
            canonical_context=teacher_ctx,
            correlation_id=f"corr_{uuid4().hex}", idempotency_key=f"cfg:{uuid4().hex}",
        ).policy_uuid
        db.session.commit()
        _fund(seat_id=ids["student_seat_id"], class_id=ids["class_id"])
        bought = execute_purchase_insurance(
            canonical_context=student_ctx, policy_uuid=policy_uuid, idempotency_key=f"ins:{uuid4().hex}",
        )
        db.session.commit()
        today = canonical_temporal_resolver(
            CLASS_LEVEL_EVALUATION, canonical_execution_context=student_ctx,
            primitive="current_evaluation_day", reference_time_utc=datetime.now(timezone.utc),
        ).evaluation_date
        filed = submit_insurance_claim(
            canonical_context=student_ctx, entitlement_id=bought.entitlement_id,
            claim_subject={"claimed_dates": [{"date": today.isoformat(), "hours": "2", "explanation": "sent home sick"}]},
        )
        assert filed.success, filed.error_message
        db.session.commit()
        claim_id = filed.claim_id
    _login_teacher(app, client, ids)

    html = client.get(f"/admin/insurance/claim/{claim_id}").get_data(as_text=True)
    assert "sent home sick" in html
    assert f'name="approve_hours-{today.isoformat()}"' in html

    resp = client.post(
        f"/admin/insurance/claim/{claim_id}",
        data={"status": "approved", f"approve_hours-{today.isoformat()}": "1.5",
              f"approve_note-{today.isoformat()}": "Left at 1:30"},
        follow_redirects=True,
    )
    assert b"Claim approved." in resp.data
    with app.app_context():
        rows = insurance_claim_service.list_productivity_dates_for_claim(claim_id, class_id=ids["class_id"])
        assert rows[0].teacher_approved_hours == Decimal("1.50")
        assert rows[0].adjustment_note == "Left at 1:30"
