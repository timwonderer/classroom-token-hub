"""Every state-changing browser fetch must carry a CSRF token (finding 33).

The application suite runs with ``WTF_CSRF_ENABLED=False`` (conftest.py), so no
request-level test can observe a missing ``X-CSRFToken`` — the header's absence
is invisible to all 2,997 of them and shows up only in a browser, as a 400 the
route never sees. This source-level guard is the only gate that can detect it.

``AppCore.csrfFetch`` already existed and nine of ten POST sites used it. What
was missing was anything preventing a tenth from calling ``fetch`` directly,
which is how the hall-pass verification link came to be unrotatable and how
sysadmin passkey deletion came to be unreachable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.guards.csrf_fetch_detector import (
    find_unprotected_state_changing_fetches,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCANNED_ROOTS = ("templates", "static/js")


def _client_sources() -> list[Path]:
    files: list[Path] = []
    for root in SCANNED_ROOTS:
        for path in (REPO_ROOT / root).rglob("*"):
            if path.is_file() and path.suffix in {".html", ".js"}:
                files.append(path)
    return sorted(files)


def test_no_state_changing_fetch_omits_its_csrf_token():
    """The live assertion: the tree contains no unprotected mutation."""
    violations = []
    for path in _client_sources():
        violations += find_unprotected_state_changing_fetches(
            path.read_text(encoding="utf-8", errors="replace"),
            str(path.relative_to(REPO_ROOT)),
        )

    assert not violations, (
        "state-changing fetch() calls without a CSRF token — Flask-WTF rejects "
        "these with 400 before the route runs, so the feature is disabled, not "
        "degraded. Route them through window.AppCore.csrfFetch:\n  "
        + "\n  ".join(str(v) for v in violations)
    )


# --------------------------------------------------------------------------
# Mutation proofs — SOP-TEST-003 §IX.A
#
# The tree is compliant, so the assertion above passes whether or not the
# detector works. These feed it the exact constructions that shipped.
# --------------------------------------------------------------------------

def test_detector_reports_the_hall_pass_rotation_defect_verbatim():
    """Finding 32, exactly as it was written."""
    shipped = (
        "    fetch('/api/hall-pass/verify-token/rotate', "
        "{method: 'POST', headers: {'Content-Type': 'application/json'}})\n"
        "        .then(r => r.json())\n"
    )
    violations = find_unprotected_state_changing_fetches(shipped, "admin_hall_pass.html")
    assert len(violations) == 1
    assert violations[0].method == "POST"


def test_detector_reports_the_sysadmin_passkey_defect_verbatim():
    """Finding 34, exactly as it was written — a DELETE, not a POST."""
    shipped = """
                const response = await fetch(`/sysadmin/passkey/0/delete`.replace('/0/', `/${credentialId}/`), {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
"""
    violations = find_unprotected_state_changing_fetches(shipped, "system_admin_passkey_settings.html")
    assert len(violations) == 1
    assert violations[0].method == "DELETE"


@pytest.mark.parametrize("verb", ["POST", "PUT", "PATCH", "DELETE"])
def test_detector_covers_every_state_changing_verb(verb):
    source = "fetch('/x', {method: '%s', headers: {'Content-Type': 'application/json'}})" % verb
    assert len(find_unprotected_state_changing_fetches(source)) == 1


def test_detector_accepts_the_canonical_helper():
    """``csrfFetch`` is not ``fetch``; the helper must never be reported."""
    source = (
        "window.AppCore.csrfFetch('/api/x', {method: 'POST', "
        "headers: {'Content-Type': 'application/json'}})"
    )
    assert find_unprotected_state_changing_fetches(source) == []


def test_detector_accepts_an_inline_token():
    """Attaching the header by hand is still correct, if less tidy."""
    source = (
        "fetch('/api/x', {method: 'POST', headers: "
        "{'Content-Type': 'application/json', 'X-CSRFToken': token}})"
    )
    assert find_unprotected_state_changing_fetches(source) == []


def test_detector_ignores_reads():
    """GET and HEAD carry no CSRF requirement and must not be flagged."""
    assert find_unprotected_state_changing_fetches("fetch('/api/x')") == []
    assert find_unprotected_state_changing_fetches("fetch('/api/x', {method: 'GET'})") == []


def test_detector_is_not_fooled_by_a_neighbouring_call():
    """A protected call next door must not vouch for an unprotected one.

    The near miss that matters: the real defect sat in a file where four other
    POSTs did attach the token, so any check with a fuzzy window would have
    called it compliant.
    """
    source = (
        "fetch('/a', {method: 'POST', headers: {'X-CSRFToken': t}});\n"
        "fetch('/b', {method: 'POST', headers: {'Content-Type': 'application/json'}});\n"
    )
    violations = find_unprotected_state_changing_fetches(source)
    assert len(violations) == 1, violations
    assert "/b" in violations[0].excerpt
