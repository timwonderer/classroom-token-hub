"""Structural guard: no process-local workflow state in ``app/``.

Incident 2026-10-01: pending hall-pass requests lived in a module-level dict
that request handlers mutated. With two gunicorn workers each process had its
own copy, and teachers' Approve and Reject failed about half the time. SOP-DEP-001
permits more than one worker only while no such state exists; this guard is what
makes that condition checkable.

The detector lives in ``tests/guards/module_level_workflow_state.py``. The
mutation proofs below feed it the spellings a future change would really use and
assert each is reported (SOP-TEST-003 §IX.A), so a green run means "no
violation" rather than "the detector stopped detecting".
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.guards.module_level_workflow_state import ALLOWLIST, find_violations

REPO = Path(__file__).resolve().parents[1]


def _app_sources():
    for path in sorted((REPO / "app").rglob("*.py")):
        yield str(path.relative_to(REPO)), path.read_text(encoding="utf-8")


def test_no_module_level_mutable_state_is_mutated_by_app_code():
    violations = [
        violation
        for path, source in _app_sources()
        for violation in find_violations(path, source)
    ]
    assert not violations, "\n".join(str(v) for v in violations)


@pytest.mark.parametrize("entry", sorted(ALLOWLIST), ids=lambda e: f"{e[0]}::{e[1]}")
def test_each_allowlist_entry_is_still_real_and_still_detected(entry):
    """An allowlisted name the detector no longer finds is either gone (remove
    the entry) or hidden by a detector regression. Both must be noticed (§IX.A.4)."""
    path, name = entry
    source = (REPO / path).read_text(encoding="utf-8")
    found = find_violations("app/not_allowlisted.py", source)
    assert name in {violation.name for violation in found}, entry


def test_the_original_defect_is_reported():
    """The hall-pass queue as it stood on main before this guard (2026-10-01)."""
    source = subprocess.run(
        ["git", "show", "ec1642f14:app/services/hall_pass_request_queue.py"],
        cwd=REPO, capture_output=True, text=True,
    )
    if source.returncode != 0:
        pytest.skip("history not available in this checkout")
    found = find_violations("app/services/hall_pass_request_queue.py", source.stdout)
    assert {violation.name for violation in found} == {"_PENDING_REQUESTS"}


@pytest.mark.parametrize("snippet", [
    # The 2026-10-01 shape, condensed: annotated dict, item write, pop under a lock.
    "_PENDING: dict[str, object] = {}\n"
    "def enqueue(r):\n    with _LOCK:\n        _PENDING[r.id] = r\n",
    "_PENDING = {}\ndef take(i):\n    return _PENDING.pop(i, None)\n",
    "_PENDING = dict()\ndef forget(i):\n    del _PENDING[i]\n",
    "from collections import defaultdict\n_BY_CLASS = defaultdict(list)\n"
    "def add(c, r):\n    _BY_CLASS[c].append(r)\n",
    "import collections\n_RECENT = collections.deque(maxlen=50)\n"
    "def note(r):\n    _RECENT.appendleft(r)\n",
    "_SEEN = set()\ndef mark(k):\n    _SEEN.add(k)\n",
    "_QUEUE = []\nclass Q:\n    def put(self, r):\n        _QUEUE.append(r)\n",
    "_STATE = {}\ndef claim(k):\n    return _STATE.setdefault(k, object())\n",
    # Through a local alias, the spelling that defeats a name-only check.
    "_PENDING = {}\ndef enqueue(r):\n    store = _PENDING\n    store[r.id] = r\n",
    # Rebinding module state from a request.
    "_ACTIVE = []\ndef replace(rows):\n    global _ACTIVE\n    _ACTIVE = list(rows)\n",
    "_COUNTS = {}\ndef bump(k):\n    _COUNTS[k] = _COUNTS.get(k, 0) + 1\n",
    # Declared inside a module-level try, as optional-import code does.
    "try:\n    import x\nexcept ImportError:\n    x = None\n_CACHE = {}\n"
    "def put(k, v):\n    _CACHE.update({k: v})\n",
])
def test_mutation_proof__each_process_local_write_is_reported(snippet):
    assert find_violations("app/services/example.py", snippet), snippet


@pytest.mark.parametrize("snippet", [
    # True constants: built at import, only read afterwards.
    "ALLOWED = {'a', 'b'}\ndef ok(x):\n    return x in ALLOWED\n",
    "LABELS = {'x': 'X'}\ndef label(k):\n    return LABELS.get(k, k)\n",
    "ORDER = ['a', 'b']\ndef first():\n    return sorted(ORDER)[0]\n",
    # Filled at import time, not by a function.
    "TABLE = {}\nfor k in 'ab':\n    TABLE[k] = k.upper()\n",
    # A local of the same name shadows the module constant.
    "ROWS = []\ndef build():\n    ROWS = []\n    ROWS.append(1)\n    return ROWS\n",
    "ROWS = []\ndef build(ROWS):\n    ROWS.append(1)\n",
    # A copy is not the module's container.
    "BASE = {'a': 1}\ndef merged(extra):\n    out = dict(BASE)\n    out.update(extra)\n    return out\n",
    # Prose.
    '"""Never keep state in a module-level dict such as _PENDING = {}."""\n',
])
def test_mutation_proof__constants_and_locals_are_not_reported(snippet):
    assert find_violations("app/services/example.py", snippet) == [], snippet


def test_allowlist_is_honoured_only_for_its_own_module():
    snippet = "_table_names_cache = {}\ndef f(k):\n    _table_names_cache[k] = 1\n"
    assert find_violations("app/routes/admin.py", snippet) == []
    assert find_violations("app/routes/api.py", snippet)
