"""Detection of the browser's own alert/confirm/prompt dialogs (SPEC-DES-001 §X).

Those dialogs are drawn by the browser, not the page: they are off-system, and
in-app browsers may not show them at all. On 2026-10-20 the Google app's iOS
browser returned an empty PIN from one without displaying it, so a student's
hall-pass request never left the page. ``AppCore.confirm`` / ``AppCore.prompt``
and ``data-confirm`` are the in-app replacements.

Factored out of the test so it can be fed synthetic violations (SOP-TEST-003
§IX.A). A call is reported when ``alert``, ``confirm`` or ``prompt`` is invoked
bare or through ``window``/``self``/``globalThis``/``top``/``parent``, in any
``*.js`` or ``*.html`` under ``templates/``, ``static/`` (except
``static/vendor/``) and ``app/``. A method of another object
(``AppCore.confirm(``) is not a native dialog and is not reported.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SCANNED_ROOTS = ("templates", "static", "app")
SCANNED_SUFFIXES = frozenset({".js", ".html"})
EXCLUDED_PREFIXES = ("static/vendor/",)

_CALL = re.compile(
    r"(?<![\w$.])(?:(?:window|self|globalThis|top|parent)\s*(?:\.\s*|\[\s*['\"]))?"
    r"(alert|confirm|prompt)(?:['\"]\s*\])?\("
)
# shortcut: "(" must follow the name directly, so prose such as "redemption
# prompt (Markdown supported)" is not a call; a spaced `confirm (x)` call would
# slip through. Parse JS instead if that spelling ever appears.
# `function confirm(` declares, it does not call.
_DECLARATION = re.compile(r"\bfunction\s+$")


@dataclass(frozen=True)
class Hit:
    path: str
    line: int
    call: str


def find_native_dialogs(text: str, path: str = "<text>") -> list[Hit]:
    hits = []
    for number, line in enumerate(text.splitlines(), start=1):
        for match in _CALL.finditer(line):
            if _DECLARATION.search(line[: match.start()]):
                continue
            hits.append(Hit(path, number, match.group(1)))
    return hits


def scanned_files(repo_root: Path):
    for root in SCANNED_ROOTS:
        for path in sorted((repo_root / root).rglob("*")):
            relative = path.relative_to(repo_root).as_posix()
            if path.suffix in SCANNED_SUFFIXES and path.is_file() and not relative.startswith(EXCLUDED_PREFIXES):
                yield relative, path


def scan_repository(repo_root: Path) -> list[Hit]:
    hits = []
    for relative, path in scanned_files(repo_root):
        hits.extend(find_native_dialogs(path.read_text(encoding="utf-8", errors="replace"), relative))
    return hits
