"""Detection of ``economic_engine`` reads outside the one effective-at resolver.

Owner ruling 2026-09-30: there is one authoritative answer to "which Economic
Engine version governs this class at instant t" —
``class_configuration_query_service.economic_engine_effective_at`` (and its
in-memory form, ``economic_engine_timeline``). Two readers disagreed before it:
one took the newest ``created_at``, another followed the ``class_features``
link timeline, and #1449's savings accrual built a third by ``created_at``. A
version dated for later was therefore in force to some readers and not others.

Factored out of the test so it can be fed a synthetic violation and proved to
report it (SOP-TEST-003 §IX.A). It parses Python source and reports, anywhere
but the resolver module:

* ``EconomicEngine.query`` (including through an import alias or
  ``models.EconomicEngine``);
* a read-building call — ``query``, ``get``, ``select``, ``with_entities``,
  ``join``, ``select_from``, ``execute`` … — given ``EconomicEngine`` or one of
  its columns;
* the ``economic_version`` relationship (the class-feature path to an engine);
* SQL text that reads ``economic_engine``.

Writing a new version (FEAT-CLASS-005, the class-creation listener) is not a
read and is not reported.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

RESOLVER_MODULE = "app/services/class_configuration_query_service.py"

MODEL = "EconomicEngine"

# The class-feature relationship to an engine version, removed 2026-09-30.
RELATIONSHIP = "economic_version"

_READ_CALLS = frozenset({
    "query", "get", "get_or_404", "select", "with_entities", "add_columns",
    "join", "outerjoin", "select_from", "execute", "scalar", "scalars",
    "filter", "filter_by", "order_by",
})

_SQL = re.compile(r"\b(from|join)\s+\"?economic_engine\"?\b", re.IGNORECASE)


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    excerpt: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line} — economic_engine read outside the resolver: {self.excerpt}"


def _model_names(tree: ast.AST) -> set[str]:
    names = {MODEL}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == MODEL:
                    names.add(alias.asname or alias.name)
    return names


def _is_model(node: ast.AST, names: set[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in names
    if isinstance(node, ast.Attribute):
        return node.attr == MODEL
    return False


def _mentions_model(node: ast.AST, names: set[str]) -> bool:
    while isinstance(node, ast.Attribute):
        if _is_model(node, names):
            return True
        node = node.value
    return _is_model(node, names)


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return None


def find_violations(path: str, source: str) -> list[Violation]:
    """Every direct read of ``economic_engine`` in one Python module."""
    if path.replace("\\", "/").endswith(RESOLVER_MODULE):
        return []
    tree = ast.parse(source)
    names = _model_names(tree)
    lines = source.splitlines()
    found: dict[int, Violation] = {}

    def report(node: ast.AST) -> None:
        line = getattr(node, "lineno", 0)
        excerpt = lines[line - 1].strip() if 0 < line <= len(lines) else ""
        found.setdefault(line, Violation(path, line, excerpt))

    prose = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "query" and _is_model(node.value, names):
            report(node)
        elif isinstance(node, ast.Attribute) and node.attr == RELATIONSHIP:
            report(node)
        elif isinstance(node, ast.Call) and _call_name(node) in _READ_CALLS:
            arguments = list(node.args) + [keyword.value for keyword in node.keywords]
            if any(_mentions_model(argument, names) for argument in arguments):
                report(node)
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in prose
            and _SQL.search(node.value)
        ):
            report(node)
    return sorted(found.values(), key=lambda violation: violation.line)
