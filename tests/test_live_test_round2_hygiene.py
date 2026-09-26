"""Findings 21, 22 and 23 — surfaces that named things wrongly or not at all.

None of these lost data. Each told the teacher something that was true in a
narrow sense and misleading in the sense that mattered, which is the recurring
shape of this live-test round.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.helpers.classroom_initializer import initialize_as_teacher

REPO_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# 21 — the export names the field the teacher filled in
# --------------------------------------------------------------------------

def test_student_export_labels_the_column_section(app, client):
    """"Block" is retired v1 vocabulary; the UI says Section everywhere else."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)

    response = client.get(f"/admin/export-students?class_id={classroom.class_id}")
    assert response.status_code == 200
    header = response.data.decode().split("\n")[0]

    assert "Section" in header, header
    assert "Block" not in header, (
        "the export still labels `section` with the retired v1 name"
    )


# --------------------------------------------------------------------------
# 22 — a stale tab is detectable, and a scope miss is not reported as success
# --------------------------------------------------------------------------

def test_admin_pages_stamp_the_class_they_were_rendered_for(app, client):
    """Without the stamp a page cannot know its own context has moved."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)

    page = client.get("/admin/students").data.decode()

    assert 'name="rendered-class-id"' in page
    assert classroom.class_id in page
    assert 'id="stale-class-context"' in page, "no banner for the page to raise"


def test_onboarding_status_reports_the_active_class(app, client):
    """The poll every admin page already makes must answer "which class am I in"."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)

    payload = client.get("/admin/onboarding/status").get_json()

    assert payload["status"] == "success"
    assert payload["active_class_id"] == classroom.class_id


def test_a_credit_that_paid_nobody_is_not_flashed_as_success(app, client):
    """Zero students paid after deliberately selecting some is never success.

    Asserted at the source because the live trigger — a second tab moving the
    session's class — is browser state a request-level test cannot reproduce.
    What is testable is that the zero branch exists and is not styled 'success'.
    """
    source = (REPO_ROOT / "app" / "routes" / "admin.py").read_text(encoding="utf-8")
    assert "if applied_count == 0:" in source, (
        "no distinct handling for a manual credit that paid nobody"
    )
    marker = source.index("if applied_count == 0:")
    branch = source[marker: marker + 1200]
    assert "'warning'" in branch, "a credit that paid nobody is still styled success"
    assert "another" in branch and "tab" in branch, (
        "the message does not name the cause the teacher needs to act on"
    )


# --------------------------------------------------------------------------
# 23 — identity-resolution failures go to the structured log
# --------------------------------------------------------------------------

def test_context_resolver_emits_no_print_calls():
    """print() bypasses correlation id, actor, class context and level filtering.

    Asserted against the parsed tree rather than the source text: the comment
    explaining why the calls were removed contains the word itself, and a naive
    substring check matches it — which is how the first attempt at this fix
    reported a failure that did not exist.
    """
    path = REPO_ROOT / "app" / "services" / "context_resolver.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    prints = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
    ]
    assert not prints, (
        f"{len(prints)} print() call(s) in the canonical context resolver: "
        + ", ".join(str(n.lineno) for n in prints)
    )


def test_context_resolver_has_a_module_logger():
    source = (REPO_ROOT / "app" / "services" / "context_resolver.py").read_text(encoding="utf-8")
    assert "logger = logging.getLogger(__name__)" in source
    assert "logger.warning(" in source, "the failure branches log nothing at all"
