"""Fixture states for admin templates.

Presentation contracts mirror what the routes pass; values are fixed and
fictional. ``admin_layout`` supplies the authenticated shell through the real
layout view-model builder.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from flask import flash

from app.forms import AdminClaimProcessForm, AnnouncementForm
from app.models import Announcement
from tests.a11y_fixtures import register
from tests.a11y_fixtures._layout import CLASS_ID, CLASS_NAME, admin_layout

_NOW = datetime(2030, 1, 15, 12, 0, tzinfo=timezone.utc)


# ---- admin_announcements.html / admin_announcement_form.html ----------------

def _announcement(announcement_id: int, title: str, priority: str, **extra) -> Announcement:
    # A transient model instance: real presentation methods, never added to a session.
    row = Announcement(
        id=announcement_id, created_by_seat_id=1, class_id=CLASS_ID, title=title,
        message="Bring a calculator tomorrow.\nQuiz on stoichiometry.", priority=priority,
        is_active=extra.pop("is_active", True), created_at=_NOW - timedelta(days=1),
        expires_at=extra.pop("expires_at", None),
    )
    row.expires_on = extra.pop("expires_on", None)
    return row


register("admin_announcements.html", "populated", lambda: {
    **admin_layout(current_page="announcements"),
    "active_class_label": CLASS_NAME,
    "announcements": [
        _announcement(1, "Quiz tomorrow", "urgent"),
        _announcement(2, "Lab goggles", "high"),
        _announcement(3, "Welcome back", "normal", expires_at=_NOW + timedelta(days=3), expires_on=date(2030, 1, 18)),
        _announcement(4, "Old reminder", "low", is_active=False, expires_at=_NOW - timedelta(days=2),
                      expires_on=date(2030, 1, 13)),
    ],
}, path="/admin/announcements", actor="teacher")


def _announcement_create(*, errors: bool = False):
    def build():
        form = AnnouncementForm()
        form.class_id.data = CLASS_ID
        if errors:
            form.title.errors = ["This field is required."]
            form.message.errors = ["This field is required."]
        return {**admin_layout(current_page="announcements"), "form": form, "action": "Create",
                "active_class_label": CLASS_NAME}
    return build


register("admin_announcement_form.html", "create", _announcement_create(), path="/admin/announcements/create", actor="teacher")
register("admin_announcement_form.html", "create-with-errors", _announcement_create(errors=True),
         path="/admin/announcements/create", actor="teacher")
register("admin_announcement_form.html", "edit-with-preview", lambda: {
    **admin_layout(current_page="announcements"),
    "form": AnnouncementForm(),
    "action": "Edit",
    "announcement": {"title": "Quiz tomorrow", "message": "Bring a calculator.", "priority_level": "danger",
                     "priority_icon": "priority_high"},
    "teacher_block": {"class_label": CLASS_NAME},
}, path="/admin/announcements/edit/1", actor="teacher")


# ---- admin_payroll_correction.html ------------------------------------------

def _correction_rows():
    return [
        {"seat_id": 11, "student_name": "Sam Student", "display_unpaid_time": "1h 30m", "display_amount": "$4.50",
         "display_status": "Proposed", "approvable": True},
        {"seat_id": 12, "student_name": "Riley Learner", "display_unpaid_time": "45m", "display_amount": "$0.00",
         "display_status": "Needs review: records do not match what was paid; use Manual Payment if pay is owed",
         "approvable": False},
        {"seat_id": 13, "student_name": "Jordan Pupil", "display_unpaid_time": "2h", "display_amount": "$6.00",
         "display_status": "Paid Oct 03", "approvable": False},
    ]


register("admin_payroll_correction.html", "proposals", lambda: {
    **admin_layout(current_page="payroll"),
    "view": {"class_label": CLASS_NAME, "rows": _correction_rows(), "has_approvable": True,
             "display_proposed_total": "$4.50", "display_expires_on": "Oct 31, 2030"},
}, path="/admin/payroll/correction", actor="teacher")
register("admin_payroll_correction.html", "nothing-to-correct", lambda: {
    **admin_layout(current_page="payroll"),
    "view": {"class_label": CLASS_NAME, "rows": [], "has_approvable": False,
             "display_proposed_total": "$0.00", "display_expires_on": "Oct 31, 2030"},
}, path="/admin/payroll/correction", actor="teacher")


# ---- admin_process_claim.html -----------------------------------------------

def _policy(**overrides):
    values = dict(title="Lunch Replacement Cover", reimbursement_percentage=80.0, waiting_period_days=3)
    values.update(overrides)
    return SimpleNamespace(**values)


def _contract(**overrides):
    values = dict(
        coverage_effective_date=date(2030, 1, 3), coverage_start_utc=_NOW - timedelta(days=15),
        claim_window_days=14, period_allowance=4, period_consumed=1, allowance_unit="claim",
        allowance_per_week=2, maximum_policy_payout=Decimal("20.00"), remaining_period_cap=Decimal("16.00"),
        filed_within_window=True, period_start_utc=_NOW - timedelta(days=10), period_end_utc=_NOW + timedelta(days=4),
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _claim(status: str, **overrides):
    values = dict(
        id="claim-a11y-1", student_name="Sam Student", submitted_at=_NOW - timedelta(days=2),
        decided_at=None, status=status, student_first_name="Sam", description="Lunch was lost on the bus.",
        additional_information=None, filing_window_override_reason=None, decision_note=None,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _process_claim(*, claim_type: str, claim, **extra):
    def build():
        extras = dict(extra)  # a fixture builds the same context every time it is called
        form = AdminClaimProcessForm()
        base = {
            **admin_layout(current_page="insurance"),
            "claim": claim, "claim_type": claim_type, "policy": _policy(),
            "contract": extras.pop("contract", _contract()), "productivity": None, "hourly_rate": None,
            "reimbursement_percentage": 80.0, "source_transaction": None, "estimated_payout": None,
            "waiting_period_days": 3, "filing_window_exceeded": False,
            "period_first_day": date(2030, 1, 5), "period_last_day": date(2030, 1, 18),
            "period_resets_on": date(2030, 1, 19),
            "claims_stats": SimpleNamespace(submitted=1, approved=2, rejected=0), "form": form,
        }
        base.update(extras)
        return base
    return build


_TRANSACTION = SimpleNamespace(description="Cafeteria lunch", timestamp=_NOW - timedelta(days=4), amount=Decimal("-4.50"))
register("admin_process_claim.html", "transaction-awaiting-decision", _process_claim(
    claim_type="TRANSACTION", claim=_claim("SUBMITTED"), source_transaction=_TRANSACTION,
    estimated_payout=Decimal("3.60")), path="/admin/insurance/claim/claim-a11y-1", actor="teacher")
register("admin_process_claim.html", "transaction-filed-late", _process_claim(
    claim_type="TRANSACTION", claim=_claim("SUBMITTED"), source_transaction=_TRANSACTION,
    estimated_payout=Decimal("3.60"), filing_window_exceeded=True,
    contract=_contract(filed_within_window=False)), path="/admin/insurance/claim/claim-a11y-1", actor="teacher")
register("admin_process_claim.html", "transaction-decided", _process_claim(
    claim_type="TRANSACTION",
    claim=_claim("REJECTED", decided_at=_NOW - timedelta(days=1), decision_note="Receipt did not match.",
                 filing_window_override_reason="Teacher allowed a late filing."),
    source_transaction=_TRANSACTION, estimated_payout=Decimal("3.60")), path="/admin/insurance/claim/claim-a11y-1", actor="teacher")


def _productivity():
    return SimpleNamespace(
        guidance_exceeded=True, expected_weekly_hours=Decimal("4.0"), additional_information="Was away at a meet.",
        dates=[
            SimpleNamespace(claim_date=date(2030, 1, 8), student_claimed_hours=Decimal("2.0"),
                            already_worked_seconds=3600, student_explanation="Lab was closed.",
                            teacher_approved_hours=None, adjustment_note=None),
            SimpleNamespace(claim_date=date(2030, 1, 9), student_claimed_hours=Decimal("1.5"),
                            already_worked_seconds=0, student_explanation="Field trip.",
                            teacher_approved_hours=Decimal("1.0"), adjustment_note="Half the shift was covered."),
        ],
    )


register("admin_process_claim.html", "productivity-awaiting-decision", _process_claim(
    claim_type="PRODUCTIVITY", claim=_claim("SUBMITTED", additional_information="Was away at a meet."),
    productivity=_productivity(), hourly_rate=Decimal("10.00"), estimated_payout=Decimal("28.00"),
    contract=_contract(allowance_unit="date")), path="/admin/insurance/claim/claim-a11y-1", actor="teacher")
register("admin_process_claim.html", "productivity-decided", _process_claim(
    claim_type="PRODUCTIVITY", claim=_claim("APPROVED", decided_at=_NOW - timedelta(days=1)),
    productivity=_productivity(), hourly_rate=Decimal("10.00"), estimated_payout=Decimal("28.00"),
    contract=_contract(allowance_unit="date")), path="/admin/insurance/claim/claim-a11y-1", actor="teacher")


# ---- admin_view_issue.html --------------------------------------------------

from app.services.ledger_correction_service import PurchaseResolutionEligibility  # noqa: E402


def _issue(status: str, **overrides) -> dict:
    values = {
        "id": 42, "status": status, "student_display_name": "Sam Student", "class_label": CLASS_NAME,
        "category": {"name": "Store purchase"}, "issue_type": "transaction", "related_transaction_id": 7,
        "student_explanation": "I was charged twice for the same item.", "student_expected_outcome": "A refund.",
        "submitted_at": _NOW - timedelta(days=3), "updated_at": _NOW - timedelta(days=1),
        "created_at": _NOW - timedelta(days=3), "escalated_at": None, "escalation_reason": None,
        "teacher_resolution": None, "teacher_reviewed_at": None, "teacher_notes": None,
        "teacher_diagnostic_note": None, "sysadmin_notes": None, "sysadmin_resolved_at": None,
        "closed_at": None, "closed_by_type": None,
        "context_snapshot": {
            "transaction": {"id": 7, "amount": -4.5, "description": "Cafeteria lunch", "account_type": "checking",
                            "posting_state": "posted"},
            "balances": {"checking": 20.0, "savings": 5.0, "total": 25.0},
            "recent_transactions": [
                {"id": 7, "amount": -4.5, "description": "Cafeteria lunch", "timestamp": "2030-01-12T11:00:00Z"},
                {"id": 6, "amount": 10.0, "description": "Payroll", "timestamp": "2030-01-10T09:00:00Z"},
            ],
        },
        "page_url": "/student/shop", "system_metadata": None, "eligible_for_reward": False,
        "share_class_name_with_sysadmin": False, "resolution_actions": [], "status_history": [],
        "_resolution_actions_count": 0,
    }
    values.update(overrides)
    return values


def _view_issue(issue: dict, purchase_resolution=None):
    def build():
        return {
            **admin_layout(current_page="issues"), "page_title": f"Issue #{issue['id']}", "issue": issue,
            "purchase_resolution": purchase_resolution, "issue_ref": "issue-ref-a11y-42",
            "format_utc_iso": lambda dt: dt.isoformat().replace("+00:00", "Z") if dt else None,
        }
    return build


_ACTION = {"action_type": "manual_credit", "action_description": "Credited $4.50", "performed_by_type": "teacher",
           "performed_by_public_id": "t-1", "related_transaction_id": 7, "amount_changed": 4.5,
           "before_value": None, "after_value": None, "created_at": _NOW - timedelta(hours=5)}
_HISTORY = [
    {"previous_status": None, "new_status": "OPEN", "changed_at": _NOW - timedelta(days=3),
     "changed_by_type": "student", "changed_by_public_id": "s-1", "notes": None},
    {"previous_status": "OPEN", "new_status": "CLOSED", "changed_at": _NOW - timedelta(hours=5),
     "changed_by_type": "teacher", "changed_by_public_id": "t-1", "notes": "Refunded."},
]

register("admin_view_issue.html", "open-purchase-reversible", _view_issue(
    _issue("OPEN"), PurchaseResolutionEligibility(True, "")), path="/admin/issues/issue-ref-a11y-42", actor="teacher")
register("admin_view_issue.html", "open-purchase-not-reversible", _view_issue(
    _issue("TEACHER_REVIEW"), PurchaseResolutionEligibility(False, "This transaction has already been reversed.")),
    path="/admin/issues/issue-ref-a11y-42", actor="teacher")
register("admin_view_issue.html", "escalated-to-developer", _view_issue(_issue(
    "ESCALATED_TO_DEV", escalated_at=_NOW - timedelta(days=1), escalation_reason="Needs developer investigation",
    teacher_diagnostic_note="Charge appears twice in the ledger.")), path="/admin/issues/issue-ref-a11y-42", actor="teacher")
register("admin_view_issue.html", "developer-resolved", _view_issue(_issue(
    "DEV_RESOLVED", escalated_at=_NOW - timedelta(days=2), escalation_reason="Needs developer investigation",
    sysadmin_notes="Duplicate posting removed.", sysadmin_resolved_at=_NOW - timedelta(hours=8))),
    path="/admin/issues/issue-ref-a11y-42", actor="teacher")
register("admin_view_issue.html", "closed-with-history", _view_issue(_issue(
    "CLOSED", teacher_resolution="Refunded the duplicate charge.", teacher_notes="Verified with the receipt.",
    teacher_reviewed_at=_NOW - timedelta(hours=6), closed_at=_NOW - timedelta(hours=5), closed_by_type="teacher",
    resolution_actions=[_ACTION], _resolution_actions_count=1, status_history=_HISTORY)),
    path="/admin/issues/issue-ref-a11y-42", actor="teacher")


# ---- student_detail.html ----------------------------------------------------
#
# The page is one template with seven Bootstrap tab panes; axe cannot see a
# hidden pane, so each state reveals one the way a teacher would. All states
# share one fully populated presentation context.


_POSTED = SimpleNamespace(value="posted")


def _detail_context(*, populated: bool = True) -> dict:
    scans = [
        SimpleNamespace(id=101, timestamp=_NOW - timedelta(hours=3), status="active", mechanism="tap",
                        reason_code=None, period="a"),
        SimpleNamespace(id=102, timestamp=_NOW - timedelta(hours=2), status="inactive", mechanism="teacher_entry",
                        reason_code="forgot_tap_out", period="a"),
    ]
    interval = SimpleNamespace(
        opened_at=_NOW - timedelta(hours=3), closed_at=_NOW - timedelta(hours=2), duration_label="1h 0m",
        settlement_label="Paid", amount=6.0, eligibility_label="Eligible", credited_seconds=3600,
        evidence_message="Matches payroll record.", opening_event_id=101, closing_event_id=102,
        original_payroll_records=[SimpleNamespace(event_id=9, recorded_at=_NOW - timedelta(hours=1))],
        payroll_event_id=None, payroll_history_url=None, pricing_inputs=None, source_events=scans,
        correction_url="/admin/student/1/attendance-correction/101/102",
    )
    open_interval = SimpleNamespace(
        opened_at=_NOW - timedelta(hours=1), duration_label="1h 0m", bounded_at_day_end=False, source_events=scans[:1],
    )
    base = {
        **admin_layout(current_page="students"),
        "display_timezone": "America/Los_Angeles",
        "student": SimpleNamespace(id=1), "identity_view": SimpleNamespace(
            first_name="Sam", last_name="Student", full_name="Sam Student", notes="Sits near the window."),
        "student_has_completed_setup": True,
        "reset_code": None, "reset_code_expires_at": None, "reset_code_is_active": False,
        "join_codes": {CLASS_NAME: "A11YTEST"},
        "scoped_checking_balance": 20.0, "scoped_savings_balance": 5.0, "scoped_total_earnings": 120.5,
        "hall_pass_balance": 3, "active_insurance": SimpleNamespace(
            policy=SimpleNamespace(title="Lunch Replacement Cover"), premiums_current=True),
        "transactions": [
            SimpleNamespace(id=7, timestamp=_NOW - timedelta(days=1), account_type="checking", amount=-4.5,
                            description="Cafeteria lunch", posting_state=_POSTED, type="purchase"),
            SimpleNamespace(id=6, timestamp=_NOW - timedelta(days=2), account_type="checking", amount=10.0,
                            description="Payroll", posting_state=_POSTED, type="payroll"),
        ],
        "entitlements": [
            SimpleNamespace(purchase_date=_NOW - timedelta(days=3), status="purchased", redemption_details=None,
                            store_item=SimpleNamespace(name="Homework pass", item_type="delayed")),
            SimpleNamespace(purchase_date=_NOW - timedelta(days=9), status="redeemed", redemption_details="Used in lab",
                            store_item=SimpleNamespace(name="Snack", item_type="immediate")),
        ],
        "latest_attendance_event": SimpleNamespace(period="a", reason="Late arrival", status="active",
                                                   timestamp=_NOW - timedelta(hours=1)),
        "attendance_events": scans, "attendance_intervals": [interval], "attendance_open_intervals": [open_interval],
        "attendance_unpaired_events": scans[:1], "attendance_completed_count": 1,
        "attendance_older_url": "/admin/student/1?attendance_before=100", "attendance_newest_url": "/admin/student/1",
        "attendance_historical_evidence_limited": True, "attendance_estimate_incomplete": True,
        "payroll_event_history": [
            {"payroll_event_id": 9, "timestamp": _NOW - timedelta(days=2), "type": "payroll", "amount": 10.0,
             "display_amount": "$10.00", "notes": "Weekly payroll"},
            {"payroll_event_id": 8, "timestamp": None, "type": None, "amount": None, "display_amount": "—",
             "notes": None},
        ],
        "rent_enabled": True,
        "rent_privileges": [SimpleNamespace(name="Window seat", description="Choose a seat by the window.",
                                            source="Rent")],
        "rent_view": SimpleNamespace(
            current_period=SimpleNamespace(is_paid=False, is_past_due=True, is_waived=False),
            display_current_due_date="Jan 10, 2030", display_total_due="$50.00", display_amount_paid="$20.00",
            display_remaining_amount="$30.00"),
    }
    if not populated:
        base.update(
            transactions=[], entitlements=[], latest_attendance_event=None, attendance_events=[],
            attendance_intervals=[], attendance_open_intervals=[], attendance_unpaired_events=[],
            attendance_completed_count=0, attendance_older_url=None, attendance_newest_url=None,
            attendance_historical_evidence_limited=False, attendance_estimate_incomplete=False,
            payroll_event_history=[], active_insurance=None, rent_enabled=False, rent_privileges=[],
            rent_view=None, join_codes={}, scoped_total_earnings=None, hall_pass_balance=0,
            student_has_completed_setup=False,
            reset_code="482916", reset_code_expires_at=_NOW + timedelta(minutes=10), reset_code_is_active=True,
        )
    return base


for _tab in ("overview", "transactions", "items", "attendance", "housing", "payroll", "settings"):
    register("student_detail.html", f"{_tab}-tab", lambda: _detail_context(), path="/admin/student/1", actor="teacher",
             interact=() if _tab == "overview" else (f"#{_tab}-tab",))
for _tab in ("overview", "attendance", "payroll", "settings"):
    register("student_detail.html", f"new-student-{_tab}-tab", lambda: _detail_context(populated=False),
             path="/admin/student/1", actor="teacher", interact=() if _tab == "overview" else (f"#{_tab}-tab",))
