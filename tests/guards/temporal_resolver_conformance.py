"""Detection of time logic outside ``canonical_temporal_resolver`` (SPEC-TIME-001 §XII, §XIII).

SPEC-TIME-001 makes ``app/utils/canonical_temporal_resolver.py`` the only place
that reads the clock, converts between timezones, builds day or period
boundaries, or does date and duration arithmetic. Every other module obtains
those values from ``canonical_temporal_resolver(...)`` primitives.

Its predecessor, ``tests/dom/operation/test_time_money_guardrails.py``, scanned
``tests/dom/app`` after a 2026-07-18 move, a directory that does not exist, so
it checked zero files and passed for three months while the rules it named were
broken in 78 files. ``scan_repository`` therefore reports how many files it
parsed, and the test requires a floor.

Factored out of the test so it can be fed synthetic violations (SOP-TEST-003
§IX.A). Detection is over the parsed tree, not text, so comments and strings
that mention a pattern are not reported.

Not reported: ``time.perf_counter()`` / ``time.monotonic()`` request-latency
measurement for observability, which is not wall-clock or calendar time, and
parsing a submitted date string (``date.fromisoformat``), which reads input
rather than evaluating time; and ``pytz.all_timezones_set`` /
``pytz.common_timezones``, which validate or list IANA names without converting
anything.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

RESOLVER = "app/utils/canonical_temporal_resolver.py"
SCANNED_ROOT = "app"

# Names the resolver module defines for its own use; importing them elsewhere
# bypasses the primitives (SPEC-TIME-001 §I: one public temporal helper).
_RESOLVER_INTERNALS = frozenset({"utc_now", "ensure_utc", "advance_local_calendar_days"})
# Constructors of calendar or duration arithmetic.
_ARITHMETIC = frozenset({"timedelta", "relativedelta"})
_CLOCK_BASES = frozenset({"datetime", "date", "dt", "_dt", "time"})
_CLOCK_READS = frozenset({"now", "utcnow", "today", "time"})
_DATETIME_CONSTRUCTORS = frozenset({"combine", "fromtimestamp", "utcfromtimestamp"})


@dataclass(frozen=True)
class Hit:
    path: str
    line: int
    rule: str


def _call_name(func: ast.expr) -> tuple[str | None, str | None]:
    if isinstance(func, ast.Name):
        return func.id, None
    if isinstance(func, ast.Attribute):
        base = func.value
        base_name = base.id if isinstance(base, ast.Name) else (
            base.attr if isinstance(base, ast.Attribute) else None
        )
        return func.attr, base_name
    return None, None


def find_violations(source: str, path: str = "<source>") -> list[Hit]:
    """Every SPEC-TIME-001 §XII pattern in one module's source."""
    hits: list[Hit] = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith("canonical_temporal_resolver"):
            for alias in node.names:
                if alias.name in _RESOLVER_INTERNALS:
                    hits.append(Hit(path, node.lineno, f"imports resolver internal {alias.name}"))
        if not isinstance(node, ast.Call):
            continue
        name, base = _call_name(node.func)
        if name is None:
            continue
        if name in _CLOCK_READS and base in _CLOCK_BASES:
            hits.append(Hit(path, node.lineno, f"reads the clock: {base}.{name}()"))
        elif name in _RESOLVER_INTERNALS:
            hits.append(Hit(path, node.lineno, f"calls resolver internal {name}()"))
        elif name == "now" and base == "func":
            hits.append(Hit(path, node.lineno, "reads the database clock: func.now()"))
        elif name == "astimezone":
            hits.append(Hit(path, node.lineno, "converts timezone: .astimezone()"))
        elif name == "replace" and any(k.arg == "tzinfo" for k in node.keywords):
            hits.append(Hit(path, node.lineno, "assigns a timezone: .replace(tzinfo=)"))
        elif name in {"localize", "ZoneInfo"} or (name == "timezone" and base == "pytz"):
            hits.append(Hit(path, node.lineno, f"converts timezone: {name}()"))
        elif name in _ARITHMETIC:
            hits.append(Hit(path, node.lineno, f"calendar or duration arithmetic: {name}()"))
        elif name == "total_seconds":
            hits.append(Hit(path, node.lineno, "raw duration math: .total_seconds()"))
        elif name in _DATETIME_CONSTRUCTORS and base == "datetime":
            hits.append(Hit(path, node.lineno, f"builds a timestamp: datetime.{name}()"))
        elif name == "date" and isinstance(node.func, ast.Attribute) and not node.args and not node.keywords:
            hits.append(Hit(path, node.lineno, "derives a date: .date()"))
    return hits


def scan_repository(root: Path) -> tuple[list[Hit], int]:
    """(violations, number of files parsed) under ``app/``, the resolver excepted."""
    hits: list[Hit] = []
    parsed = 0
    for file in sorted((root / SCANNED_ROOT).rglob("*.py")):
        rel = file.relative_to(root).as_posix()
        if rel == RESOLVER or "__pycache__" in file.parts:
            continue
        hits.extend(find_violations(file.read_text(encoding="utf-8"), rel))
        parsed += 1
    return hits, parsed
