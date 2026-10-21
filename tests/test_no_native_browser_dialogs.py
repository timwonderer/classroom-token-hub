"""No first-party page uses the browser's own alert/confirm/prompt (SPEC-DES-001 §X).

Detector: ``tests/guards/native_browser_dialogs.py``. The mutation proofs feed
it the spellings a future change would really use, so the guard cannot go
green because it stopped seeing (SOP-TEST-003 §IX.A).
"""

from pathlib import Path

import pytest

from tests.guards.native_browser_dialogs import find_native_dialogs, scan_repository

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_no_native_browser_dialogs_in_first_party_pages():
    hits = scan_repository(REPO_ROOT)
    assert hits == [], "Use AppCore.confirm / AppCore.prompt or data-confirm:\n" + "\n".join(
        f"{h.path}:{h.line} {h.call}()" for h in hits
    )


@pytest.mark.parametrize("source", [
    "const pin = prompt('Enter your PIN:');",
    "if (!confirm('Delete?')) return;",
    "alert('Saved');",
    '<button onclick="return confirm(\'Pay this bill?\')">Pay</button>',
    '<form onsubmit="return confirm(\'Retire?\');">',
    "if (!window.confirm('Delete?')) return;",
    "window . prompt('x')",
    "globalThis.alert('x')",
    "self.confirm('x')",
    "window['confirm']('x')",
    "x = cond && confirm('sure?')",
])
def test_mutation_proof_reports_each_native_dialog_spelling(source):
    assert find_native_dialogs(source), source


@pytest.mark.parametrize("source", [
    "await window.AppCore.confirm('Delete?', {danger: true})",
    "const v = await AppCore.prompt('Name it.')",
    "function confirmDialog(message) {}",
    "function confirm(message) {}",
    'placeholder: "Enter redemption prompt (Markdown supported)..."',
    "{# Advisory out-of-range alert (non-blocking) #}",
    '<button data-confirm="Pay this bill?">Pay</button>',
    "bootstrap.Modal.getOrCreateInstance(el).confirm",
])
def test_non_dialog_text_is_not_reported(source):
    assert find_native_dialogs(source) == [], source
