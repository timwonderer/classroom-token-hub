"""INV-ARC-022 §V.8 / SPEC-UI-001 §X–§XI: builders format times; templates print them, routes never format."""

from pathlib import Path

import pytest

from tests.guards.template_time_formatting import (
    find_route_time_formatting,
    find_template_time_formatting,
    scan_routes,
    scan_templates,
)

REPO = Path(__file__).resolve().parent.parent


def test_INV_ARC_022__no_template_formats_or_converts_a_time():
    hits, scanned = scan_templates(REPO)
    assert scanned >= 80, f"scanned only {scanned} templates: the guard is not looking at templates/"
    assert not hits, "Produce the display text in the page builder (SPEC-UI-001 §VII):\n" + "\n".join(
        f"{h.path}:{h.line}: {h.rule}" for h in hits
    )


@pytest.mark.parametrize("source", [
    "<td>{{ txn.timestamp | fmt_timestamp }}</td>",
    "<td>{{ row.created_at|fmt_date }}</td>",
    "{{ item.expires_at | fmt_compact_date }}",
    "{{ pass.left_at | fmt_time }}",
    "{{ row.created_at.strftime('%b %d') }}",
    "{{ row.created_at.astimezone(tz) }}",
    '<time datetime="{{ row.created_at.isoformat() }}">',
    "{% elif enrollment.coverage_start_date > now %}",
    "{% if now >= item.expires_at %}",
    "{% set waiting = not e.starts or e.starts >\n    now %}",
    "<td>{{ txn.timestamp[:10] if txn.timestamp else 'N/A' }}</td>",
])
def test_mutation_proof_reports_each_template_time_operation(source):
    assert find_template_time_formatting(source), source


@pytest.mark.parametrize("source", [
    "<td>{{ txn.timestamp_display }}</td>",
    '<time datetime="{{ row.created_at_iso }}">{{ row.created_at_display }}</time>',
    "{# fmt_timestamp used to live here #}{{ name | e }}",
    "{% elif enrollment.coverage_not_started %}",
    "<p>Right now you are covered.</p>",
])
def test_printed_display_fields_are_not_reported(source):
    assert not find_template_time_formatting(source), source


def test_SPEC_UI_001__no_route_formats_a_time():
    hits, scanned = scan_routes(REPO)
    assert scanned >= 8, f"scanned only {scanned} route modules"
    assert not hits, "Format times in the page builder (SPEC-UI-001 §XI):\n" + "\n".join(
        f"{h.path}:{h.line}: {h.rule}" for h in hits
    )


@pytest.mark.parametrize("source", [
    "label = due.strftime('%B %d, %Y')\n",
    "choices = [(t.id, f\"{t.timestamp:%b %d}\") for t in rows]\n",
    "from app.utils.temporal_display import format_timestamp\nshown = format_timestamp(ctx, row.created_at)\n",
    "shown = format_local_date(day, 'short')\n",
])
def test_mutation_proof_reports_each_route_time_format(source):
    assert find_route_time_formatting(source), source


@pytest.mark.parametrize("source", [
    "rows = build_hall_pass_history_times(ctx, requested_at=r.timestamp, left_at=None, returned_at=None)\n",
    "key = row.claim_date.isoformat()\n",
    "amount = f\"${value:.2f}\"\n",
])
def test_builder_calls_and_serialization_in_routes_are_not_reported(source):
    assert not find_route_time_formatting(source), source
