"""Detection of time formatting inside Jinja templates (INV-ARC-022 §V.8, SPEC-UI-001 §VI-§X).

Templates are pure consumers of a presentation contract: a time arrives as text
the page's builder produced through the temporal resolver, and the template
prints it. Until 2026-10-25 templates converted times themselves through the
`fmt_timestamp` / `fmt_date` / `fmt_compact_date` / `fmt_time` filters, and
the SPEC-TIME-001 1.3 migration briefly made those filters query the database
during rendering.

Factored out of the test so it can be fed synthetic violations (SOP-TEST-003
§IX.A). Reported in any `templates/**/*.html`: a `fmt_*` time filter; a
`strftime(` / `.astimezone(` / `.isoformat(` call; a comparison against
`now`/`today` inside a Jinja tag; slicing a timestamp string (`ts[:10]`).
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
    ("timestamp slicing in template", re.compile(r"(?:_at|timestamp|_time)\s*\[\s*:\s*(?:10|16|19)\s*\]")),
)


@dataclass(frozen=True)
class Hit:
    path: str
    line: int
    rule: str


_JINJA_TAG = re.compile(r"\{[%{].*?[%}]\}", re.S)
_NOW_COMPARISON = re.compile(r"(?:\b(?:now|today|now_utc|class_today)\b\s*[<>]=?|[<>]=?\s*\b(?:now|today|now_utc|class_today)\b)")


def find_template_time_formatting(text: str, path: str = "<template>") -> list[Hit]:
    hits = []
    for number, line in enumerate(text.splitlines(), start=1):
        for rule, pattern in _PATTERNS:
            if pattern.search(line):
                hits.append(Hit(path, number, rule))
    # A comparison can span lines inside one Jinja tag; check each tag whole.
    for tag in _JINJA_TAG.finditer(text):
        if _NOW_COMPARISON.search(tag.group(0)):
            number = text.count("\n", 0, tag.start()) + 1
            if Hit(path, number, "time comparison in template") not in hits:
                hits.append(Hit(path, number, "time comparison in template"))
    return hits


def scan_templates(repo_root: Path) -> tuple[list[Hit], int]:
    hits, scanned = [], 0
    for path in sorted((repo_root / "templates").rglob("*.html")):
        hits.extend(find_template_time_formatting(path.read_text(encoding="utf-8"), path.relative_to(repo_root).as_posix()))
        scanned += 1
    return hits, scanned


# SPEC-UI-001 §XI: routes resolve context and call builders; they do not format
# times. Builders call the formatters in app/utils/temporal_display.py.
_DISPLAY_FORMATTERS = frozenset({
    "format_timestamp", "format_date", "format_compact_date", "format_time", "format_local_date",
})


def find_route_time_formatting(source: str, path: str = "<route>") -> list[Hit]:
    import ast

    hits = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if name == "strftime":
                hits.append(Hit(path, node.lineno, "strftime in route"))
            elif name in _DISPLAY_FORMATTERS:
                hits.append(Hit(path, node.lineno, f"{name}() in route"))
        elif isinstance(node, ast.FormattedValue) and node.format_spec is not None \
                and "%" in ast.unparse(node.format_spec):
            hits.append(Hit(path, node.lineno, "f-string date format in route"))
    return hits


def scan_routes(repo_root: Path) -> tuple[list[Hit], int]:
    hits, scanned = [], 0
    for path in sorted((repo_root / "app" / "routes").rglob("*.py")):
        hits.extend(find_route_time_formatting(path.read_text(encoding="utf-8"), path.relative_to(repo_root).as_posix()))
        scanned += 1
    return hits, scanned
