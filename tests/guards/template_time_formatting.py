"""Detection of time formatting inside Jinja templates (INV-ARC-022 §V.8, SPEC-UI-001 §VI-§X).

Templates are pure consumers of a presentation contract: a time arrives as text
the page's builder produced through the temporal resolver, and the template
prints it. Until 2026-10-25 templates converted times themselves through the
`fmt_timestamp` / `fmt_date` / `fmt_compact_date` / `fmt_time` filters, and
the SPEC-TIME-001 1.3 migration briefly made those filters query the database
during rendering.

Factored out of the test so it can be fed synthetic violations (SOP-TEST-003
§IX.A). Reported in any `templates/**/*.html`: a `fmt_*` time filter, and a
`strftime(` / `.astimezone(` / `.isoformat(` call on a value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_PATTERNS = (
    ("time filter", re.compile(r"\|\s*fmt_(?:timestamp|date|compact_date|time)\b")),
    ("strftime in template", re.compile(r"\.strftime\s*\(")),
    ("timezone conversion in template", re.compile(r"\.astimezone\s*\(")),
    ("isoformat in template", re.compile(r"\.isoformat\s*\(")),
)


@dataclass(frozen=True)
class Hit:
    path: str
    line: int
    rule: str


def find_template_time_formatting(text: str, path: str = "<template>") -> list[Hit]:
    hits = []
    for number, line in enumerate(text.splitlines(), start=1):
        for rule, pattern in _PATTERNS:
            if pattern.search(line):
                hits.append(Hit(path, number, rule))
    return hits


def scan_templates(repo_root: Path) -> tuple[list[Hit], int]:
    hits, scanned = [], 0
    for path in sorted((repo_root / "templates").rglob("*.html")):
        hits.extend(find_template_time_formatting(path.read_text(encoding="utf-8"), path.relative_to(repo_root).as_posix()))
        scanned += 1
    return hits, scanned
