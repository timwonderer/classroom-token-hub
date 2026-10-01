"""Detection of ``payroll_settings`` queries outside the one resolver.

Operator ruling 2026-09-30: every payroll reader resolves ``payroll_settings``
through ``app/services/payroll/settings.py`` ("the row in force for class_id at
t"). A route, job or service that queries the table itself can pick "the newest
row" instead of "the row in force", which is exactly the defect that let a rate
saved mid-cycle reprice work already done (DOM-CLASS-003 §VII).

Factored out of the test so it can be fed a synthetic violation and proved to
report it (SOP-TEST-003 §IX.A). It parses Python source and reports:

* ``PayrollSettings.query`` (including through an import alias or
  ``models.PayrollSettings``);
* a query-building call — ``query``, ``get``, ``select``, ``with_entities``,
  ``join``, ``select_from`` … — given ``PayrollSettings`` or one of its columns;
* SQL text that reads or writes ``payroll_settings``.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

RESOLVER_MODULE = "app/services/payroll/settings.py"

MODEL = "PayrollSettings"

# Calls that build or run a query from the entities they are given.
_QUERY_CALLS = frozenset({
    "query", "get", "get_or_404", "select", "with_entities", "add_columns",
    "join", "outerjoin", "select_from", "execute", "scalar", "scalars",
    "delete", "update", "insert",
})

_SQL = re.compile(
    r"\b(from|join|update|into|delete\s+from|table)\s+\"?payroll_settings\"?\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    excerpt: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line} — payroll_settings read outside the resolver: {self.excerpt}"


def _model_names(tree: ast.AST) -> set[str]:
    """Local names bound to the model, including ``import ... as`` aliases."""
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
    """True if ``node`` is the model or an attribute chain rooted in it."""
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
    """Every direct read of ``payroll_settings`` in one Python module."""
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

    # Docstrings and other bare string statements are prose, not SQL.
    prose = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "query" and _is_model(node.value, names):
            report(node)
        elif isinstance(node, ast.Call) and _call_name(node) in _QUERY_CALLS:
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
