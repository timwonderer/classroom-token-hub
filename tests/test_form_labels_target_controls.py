"""Visible form labels name the control beside them (INV-ARC-020 §VI.3, §VII.C).

WAVE, 2026-10-20: the payroll manual-payment fields and the attendance-log
filters had labels whose ``for`` pointed at no element, so the controls were
named only by a placeholder or a differently worded aria-label. axe accepts
either as an accessible name, so the WCAG sweep passed them.
"""

import re

from tests.helpers.classroom_initializer import initialize_as_teacher

LABEL_FOR = re.compile(r'<label\b[^>]*\bfor="([^"]+)"')


def _orphaned_label_targets(html: str) -> set[str]:
    ids = set(re.findall(r'\bid="([^"]+)"', html))
    return {target for target in LABEL_FOR.findall(html) if target not in ids}


def test_orphaned_label_detector_reports_a_mismatched_for():
    assert _orphaned_label_targets('<label for="description">D</label><textarea id="manualDescription">') == {"description"}
    assert _orphaned_label_targets('<label for="manualDescription">D</label><textarea id="manualDescription">') == set()


def test_payroll_and_attendance_log_labels_point_at_their_controls(client, app):
    initialize_as_teacher("chemistry_p1", client, app)
    for path, controls in (
        ("/admin/payroll", ("manualDescription", "manualAmount")),
        ("/admin/attendance-log", ("filterStatus", "filterStartDate", "filterEndDate")),
    ):
        html = client.get(path).get_data(as_text=True)
        assert _orphaned_label_targets(html) == set(), path
        for control in controls:
            assert f'for="{control}"' in html, (path, control)
