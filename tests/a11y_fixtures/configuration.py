"""Configuration transfer presentation states (SPEC-CLASS-001)."""
from flask_wtf import FlaskForm
from app.services.configuration_fields import SCHEDULES, SCHEMAS
from app.services.configuration_display import FAMILY_LABELS, FIELD_LABELS, preview_sections
from tests.a11y_fixtures import register
from tests.a11y_fixtures._layout import admin_layout


def transfer_state(stage):
    def context():
        groups = {"store": [{"name": "Pencil", "activation_at": "2030-01-15",
            "auto_delist_date": None, "collective_goal_expires_at": None}],
            "payroll": {"pay_schedule_type": "weekly", "first_pay_date": "2030-01-18"}}
        return {**admin_layout(current_page="configuration_transfer"), "stage": stage,
            "form": FlaskForm(), "groups": groups, "destination": groups,
            "entries": {"store": ["Pencil"]}, "labels": FAMILY_LABELS,
            "sections": preview_sections(groups), "skipped_labels": ["Insurance"] if stage == "confirm" else [], "field_labels": FIELD_LABELS, "schedules": SCHEDULES, "schemas": SCHEMAS,
            "raw": "fictional-artifact", "inventory_digest": "fictional-digest",
            "preview": {"groups": groups, "skipped": ["insurance"], "token": "fictional-token",
                "timezone": "America/Los_Angeles", "expires_at": "Jan 20, 2030, 4:00 AM PST",
                "timing": {"Payroll effective date and time": "Jan 18, 2030, 12:00 AM PST"}},
            "result": {"skipped": [], "payroll_effective_at": "2030-01-18T08:00:00+00:00",
                "payroll_effective_display": "Jan 18, 2030, 12:00 AM PST"}}
    return context


for stage in ("start", "choose", "confirm", "done"):
    register("configuration_transfer.html", stage, transfer_state(stage),
        path="/admin/configuration/", actor="teacher",
        interact=("details summary",) if stage == "choose" else ())
