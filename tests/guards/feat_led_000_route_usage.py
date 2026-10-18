"""Detection of `FEATContext("FEAT-LED-000", ...)` openings under `app/routes/`
(`FEAT-LED-005` §VIII.5: "no code path may open `FEAT-LED-000` for this
purpose" once the cutover lands).

Factored out of the test so it can be fed a synthetic violation and proved to
report it (SOP-TEST-003 §IX.A). A route can spell the call across several
lines (``with FEATContext(\\n    "FEAT-LED-000",\\n    ...\\n):``), so this
matches over each whole file's text rather than one line at a time, and
reports the line the ``FEATContext(`` call itself starts on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_PATTERN = re.compile(r"FEATContext\(\s*[\"']FEAT-LED-000[\"']")


@dataclass(frozen=True)
class Hit:
    path: str
    line: int


def find_feat_led_000_openings(relative_path: str, text: str) -> list[Hit]:
    """Every line opening a `FEATContext("FEAT-LED-000", ...)` in one file's text."""
    hits = []
    for match in _PATTERN.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        hits.append(Hit(relative_path, line))
    return hits


def scan_routes(repo_root: Path) -> list[Hit]:
    """Every `app/routes/**/*.py` file for a FEAT-LED-000 FEATContext opening."""
    hits = []
    routes_dir = repo_root / "app" / "routes"
    if not routes_dir.is_dir():
        return hits
    for path in sorted(routes_dir.rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        hits.extend(find_feat_led_000_openings(path.relative_to(repo_root).as_posix(), text))
    return hits
