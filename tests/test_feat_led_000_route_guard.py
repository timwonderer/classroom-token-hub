"""No `app/routes/` file opens `FEATContext("FEAT-LED-000", ...)` (`FEAT-LED-005`
§VIII.5). The internal-transfer route is the only historical caller, and it
now opens `FEAT-LED-005`; this guards the cutover against a regression that
reopens the retired identity, whether on the transfer route or a new one.

The detector lives in `tests/guards/feat_led_000_route_usage.py`. The
mutation proof below feeds it the exact multi-line call shape a regression
would actually use (SOP-TEST-003 §IX.A).
"""

from __future__ import annotations

from pathlib import Path

from tests.guards.feat_led_000_route_usage import find_feat_led_000_openings, scan_routes

ROOT = Path(__file__).resolve().parents[1]


def _plant(tmp_path: Path, relative: str, text: str) -> None:
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_no_feat_led_000_opened_under_app_routes():
    hits = scan_routes(ROOT)
    assert not hits, (
        "FEAT-LED-000 opened under app/routes/ (FEAT-LED-005 §VIII.5):\n"
        + "\n".join(f"  {h.path}:{h.line}" for h in hits)
    )


def test_mutation_multiline_feat_context_is_reported(tmp_path):
    """The exact shape student.py's transfer route used before the cutover."""
    _plant(
        tmp_path,
        "app/routes/student.py",
        "with FEATContext(\n"
        '    "FEAT-LED-000",\n'
        "    idempotency_key=f\"feat:transfer:{class_id}:{seat_id}\",\n"
        "):\n"
        "    execute_account_transfer(...)\n",
    )
    hits = scan_routes(tmp_path)
    assert [(h.path, h.line) for h in hits] == [("app/routes/student.py", 1)]


def test_mutation_single_line_feat_context_is_reported(tmp_path):
    _plant(
        tmp_path,
        "app/routes/new_route.py",
        'with FEATContext("FEAT-LED-000", idempotency_key=key):\n    ...\n',
    )
    hits = scan_routes(tmp_path)
    assert [(h.path, h.line) for h in hits] == [("app/routes/new_route.py", 1)]


def test_lawful_neighbours_are_not_reported():
    """A FEAT-LED-005 opening, and a bare mention in a comment, are not violations."""
    text = (
        'with FEATContext("FEAT-LED-005", idempotency_key=key):\n'
        "    execute_account_transfer(...)\n"
        "# historically this route opened FEAT-LED-000\n"
    )
    assert find_feat_led_000_openings("app/routes/student.py", text) == []


def test_out_of_scope_paths_are_not_scanned(tmp_path):
    """A non-route file naming FEAT-LED-000 in a FEATContext call is lawful
    (FEAT-LED-000 still exists for other Ledger orchestration; only the route
    surface is retired for it)."""
    _plant(tmp_path, "app/feats/some_other_feat.py", 'FEATContext("FEAT-LED-000", idempotency_key=key)\n')
    assert scan_routes(tmp_path) == []
