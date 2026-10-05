"""Fixture states for student templates.

Presentation contracts mirror what the routes pass: ``SimpleNamespace`` view
objects for insurance, built here from fixed, fictional values.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from flask import flash

from app.forms import InsuranceClaimForm
from tests.a11y_fixtures import register
from tests.a11y_fixtures._layout import student_layout

_NOW = datetime(2030, 1, 15, 12, 0, tzinfo=timezone.utc)
_STUDENT = "Sam Student"


# ---- student_verify_recovery.html ----------------------------------------

def _recovery_code():
    return SimpleNamespace(
        id=1,
        recovery_request=SimpleNamespace(expires_at=_NOW + timedelta(minutes=30)),
    )


def _verify_recovery(*, error: bool = False, verified: bool = False):
    def build():
        if error:
            flash("Incorrect passphrase. Please try again.", "error")
        ctx = {**student_layout(current_page="verify-recovery"),
               "recovery_code": _recovery_code(), "student": _STUDENT}
        if verified:
            ctx.update(generated_code="482916", verified=True)
        return ctx
    return build


register("student_verify_recovery.html", "awaiting-passphrase", _verify_recovery(), path="/student/verify-recovery/1", actor="student")
register("student_verify_recovery.html", "wrong-passphrase", _verify_recovery(error=True), path="/student/verify-recovery/1", actor="student")
register("student_verify_recovery.html", "code-issued", _verify_recovery(verified=True), path="/student/verify-recovery/1", actor="student")


# ---- student_file_claim.html ----------------------------------------------

def _claim_policy(insurance_type: str, **overrides):
    values = dict(
        policy_uuid="policy-a11y-1", title="Lunch Replacement Cover", description="Replaces a lost lunch purchase.",
        insurance_type=insurance_type, premium=5.0, charge_frequency="weekly",
        reimbursement_percentage=80.0, payout_multiple=None, claim_window_days=14,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


_PRIOR_CLAIMS = [
    SimpleNamespace(status="approved", filed_date=_NOW - timedelta(days=9), approved_amount=4.0),
    SimpleNamespace(status="pending", filed_date=_NOW - timedelta(days=2), approved_amount=None),
]


def _file_claim(insurance_type: str, *, claimable: bool = True, prior=()):
    def build():
        form = InsuranceClaimForm()
        form.transaction_id.choices = (
            [("", "Select a transaction…"), ("11", "Jan 12 · $4.50 · Cafeteria")]
            if insurance_type == "TRANSACTION" else []
        )
        return {
            **student_layout(current_page="insurance"),
            "student": _STUDENT,
            "policy": _claim_policy(insurance_type, **({} if insurance_type == "TRANSACTION" else
                                                       {"reimbursement_percentage": None, "payout_multiple": 3.0})),
            "form": form,
            "is_transaction_type": insurance_type == "TRANSACTION",
            "is_productivity_type": insurance_type == "PRODUCTIVITY",
            "claimable": claimable,
            "prior_claims": list(prior),
            "class_today": date(2030, 1, 15),
        }
    return build


register("student_file_claim.html", "transaction-claim", _file_claim("TRANSACTION", prior=_PRIOR_CLAIMS),
         path="/student/insurance/claim/policy-a11y-1", actor="student")
register("student_file_claim.html", "productivity-claim", _file_claim("PRODUCTIVITY"),
         path="/student/insurance/claim/policy-a11y-1", actor="student")
register("student_file_claim.html", "claim-type-unsupported", _file_claim("OTHER", claimable=False),
         path="/student/insurance/claim/policy-a11y-1", actor="student")


# ---- student_view_policy.html ---------------------------------------------

def _claim_row(claim_id: int, status: str, **extra):
    values = dict(
        id=claim_id, claim_id=f"claim-{claim_id}", policy=SimpleNamespace(title="Lunch Replacement Cover"),
        status=status, approved_amount=None, claim_amount=4.5, rejection_reason=None,
        description="Lunch was lost on the bus.", teacher_notes=None,
        incident_date=_NOW - timedelta(days=5), filed_date=_NOW - timedelta(days=4),
    )
    values.update(extra)
    return SimpleNamespace(**values)


def _policy_enrollment(*, premiums_current: bool):
    policy = SimpleNamespace(
        id="policy-a11y-1", title="Lunch Replacement Cover", description="Replaces a **lost** lunch purchase.",
        premium=5.0, charge_frequency="weekly", waiting_period_days=3, max_claims_count=2,
        claim_type="TRANSACTION", autopay=True, auto_cancel_nonpay_days=14,
        entitlement_item_id="policy-a11y-1", payload={},
    )
    return SimpleNamespace(
        id="policy-a11y-1", policy=policy, contract_title=policy.title, contract_description=policy.description,
        purchase_date=_NOW - timedelta(days=20),
        coverage_start_date=_NOW - timedelta(days=17) if premiums_current else _NOW + timedelta(days=3),
        premiums_current=premiums_current, status="active",
        next_payment_due=_NOW + timedelta(days=4), covered_through=date(2030, 1, 19),
        contract_claim_time_limit_days=14, contract_period_payout_cap=15.0,
        contract_max_claims_count=2, contract_allowance_unit="claims",
    )


def _view_policy(*, premiums_current: bool, claims):
    def build():
        return {
            **student_layout(current_page="insurance"),
            "student": _STUDENT, "enrollment": _policy_enrollment(premiums_current=premiums_current),
            "claims": claims, "now": _NOW,
        }
    return build


register("student_view_policy.html", "current-with-claims", _view_policy(premiums_current=True, claims=[
    _claim_row(1, "pending"),
    _claim_row(2, "approved", approved_amount=4.0, teacher_notes="Receipt checked."),
    _claim_row(3, "rejected", rejection_reason="Filed outside the claim window."),
    _claim_row(4, "paid", approved_amount=4.0),
]), path="/student/insurance/policy/policy-a11y-1", actor="student")
register("student_view_policy.html", "premium-overdue-no-claims", _view_policy(premiums_current=False, claims=[]),
         path="/student/insurance/policy/policy-a11y-1", actor="student")
