"""Detection of deprecated symbols in first-party code (SOP-DB-002 §II, §V).

A deprecated symbol names a structure that no longer exists (a contracted model,
column or model behavior). Code that names it again either fails at import or
first use, or quietly brings back behavior that was removed on purpose.

Factored out of the test so it can be fed synthetic violations and proved to
report them (SOP-TEST-003 §IX.A). Rules, matching SOP-DB-002 §V:

* the enforced list is ``DEPRECATED_SYMBOLS.txt``: one literal per line; blank
  lines and lines starting with ``#`` are ignored;
* a match is a case-sensitive **substring** match on any line, as ``grep`` does.
  A symbol inside a longer identifier, a string literal, a comment or a template
  expression is reported. That is deliberate: ``getattr(x, "is_bundle")`` and
  ``get_default_pass_types_for_class`` reintroduce the symbol as surely as a bare
  name does. A symbol that cannot survive substring matching belongs in §VII,
  not in the file;
* the scanned set is first-party application code (§II): ``*.py``, ``*.html``,
  ``*.sh`` and ``*.js`` under ``app/``, ``templates/`` and ``scripts/``, plus
  ``*.js`` under ``static/`` except ``static/vendor/``, which is third-party.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

REGISTRY_RELATIVE = Path("docs/STANDARD_OPERATING_PROCEDURES/DATABASE/DEPRECATED_SYMBOLS.txt")

# (root, suffixes scanned under it). SOP-DB-002 §II is the authority for this set.
SCANNED_ROOTS: tuple[tuple[str, frozenset[str]], ...] = (
    ("app", frozenset({".py", ".html", ".sh", ".js"})),
    ("templates", frozenset({".py", ".html", ".sh", ".js"})),
    ("scripts", frozenset({".py", ".html", ".sh", ".js"})),
    ("static", frozenset({".js"})),
)

# Third-party code is not ours to police, and a substring could collide with it.
EXCLUDED_PREFIXES: tuple[str, ...] = ("static/vendor/",)


@dataclass(frozen=True)
class Hit:
    path: str
    line: int
    symbol: str


def parse_registry(text: str) -> list[str]:
    """The enforced symbols, in file order."""
    symbols = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        symbols.append(line)
    return symbols


def is_scanned(relative_path: str) -> bool:
    """Whether a repo-relative POSIX path is in the SOP-DB-002 §II scope."""
    if any(relative_path.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
        return False
    root, _, rest = relative_path.partition("/")
    if not rest:
        return False
    suffix = Path(relative_path).suffix
    return any(root == name and suffix in suffixes for name, suffixes in SCANNED_ROOTS)


def find_deprecated_symbols(relative_path: str, text: str, symbols: list[str]) -> list[Hit]:
    """Every (line, symbol) occurrence in one file's text."""
    hits = []
    for number, line in enumerate(text.splitlines(), start=1):
        for symbol in symbols:
            if symbol in line:
                hits.append(Hit(relative_path, number, symbol))
    return hits


def iter_scanned_files(repo_root: Path) -> list[Path]:
    """Every file under ``repo_root`` that :func:`is_scanned` admits."""
    files = []
    for name, _ in SCANNED_ROOTS:
        base = repo_root / name
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.is_file() and is_scanned(path.relative_to(repo_root).as_posix()):
                files.append(path)
    return sorted(files)


def scan_tree(repo_root: Path, symbols: list[str]) -> list[Hit]:
    hits = []
    for path in iter_scanned_files(repo_root):
        text = path.read_text(encoding="utf-8", errors="replace")
        hits.extend(find_deprecated_symbols(path.relative_to(repo_root).as_posix(), text, symbols))
    return hits
