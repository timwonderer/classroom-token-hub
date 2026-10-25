"""INV-ARC-022 §V.8 / SPEC-UI-001 §X: templates print times their builders formatted."""

from pathlib import Path

import pytest

from tests.guards.template_time_formatting import find_template_time_formatting, scan_templates

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
])
def test_mutation_proof_reports_each_template_time_operation(source):
    assert find_template_time_formatting(source), source


@pytest.mark.parametrize("source", [
    "<td>{{ txn.timestamp_display }}</td>",
    '<time datetime="{{ row.created_at_iso }}">{{ row.created_at_display }}</time>',
    "{# fmt_timestamp used to live here #}{{ name | e }}",
])
def test_printed_display_fields_are_not_reported(source):
    assert not find_template_time_formatting(source), source
