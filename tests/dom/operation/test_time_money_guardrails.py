"""
Guardrail tests to prevent regressions in money handling.

Time handling is guarded by tests/test_SPEC_TIME_001__resolver_is_the_only_time_tool.py.
From 2026-07-18 to 2026-10-23 APP_ROOT here pointed at tests/dom/app, which does
not exist, so these checks scanned nothing; the fixture now refuses an empty scan.
"""

from pathlib import Path
import re

import pytest


APP_ROOT = Path(__file__).resolve().parents[3] / "app"


def _iter_python_files():
    for path in APP_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


@pytest.fixture(scope="module")
def app_python_sources():
    """Cache all app/*.py file contents once per test module."""
    sources = []
    for path in _iter_python_files():
        sources.append((path.as_posix(), path.read_text(encoding="utf-8")))
    assert len(sources) >= 150, f"scanned only {len(sources)} files under {APP_ROOT}"
    return sources


def test_DOM_OPS_001__no_generic_float_zero_fallbacks_in_routes(app_python_sources):
    """
    Prevent reintroducing ambiguous float defaults in route logic.
    """
    allowed_line_patterns = (
        "hold_seconds = 0.0",
        "gate_hold_seconds = 0.0",
    )

    offenders = []
    for path, source in app_python_sources:
        if "/app/routes/" not in path:
            continue
        lines = source.splitlines()
        for idx, line in enumerate(lines, start=1):
            if not re.search(r"(?<![\d])0\.0(?!\d)", line):
                continue
            if any(token in line for token in allowed_line_patterns):
                continue
            offenders.append(f"{path}:{idx}")

    assert not offenders, f"Use Decimal-safe defaults or explicit non-money justification: {offenders}"
