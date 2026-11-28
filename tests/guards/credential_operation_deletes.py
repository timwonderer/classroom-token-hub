"""Detection of code that deletes ``credential_operations`` rows.

SPEC-IDEN-002 §V/§VI: a spent TOTP-replacement row is the receipt whose unique ``step_up_token_id``
refuses a replay until ``step_up_retain_until`` has passed. So a row may be removed in exactly two
ways: the retention-aware sweep (``expire_stale_operations``) and the principal's own destruction,
which the foreign key's ``ON DELETE CASCADE`` performs with the ``users`` row. Any other delete would
silently reopen the replay window.

Factored out of the test so it can be fed a synthetic violation (SOP-TEST-003 §IX.A). The rules, all
over the parsed tree of one source file:

* a ``.delete(...)`` call whose receiver chain, or a ``delete(...)`` call whose arguments, name
  ``CredentialOperation`` or the table ``credential_operations``;
* a ``.delete(...)`` whose receiver or argument is a name bound, within the same function, to
  something naming ``CredentialOperation`` or the table (``op = session.get(CredentialOperation, id)``,
  ``for op in ops``, ``table = db.metadata.tables["credential_operations"]``);
* a string that is a ``DELETE FROM`` or ``TRUNCATE`` of ``credential_operations``.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

TABLE = "credential_operations"
MODEL = "CredentialOperation"
_RAW_SQL = re.compile(r"\b(delete\s+from|truncate(\s+table)?)\s+(only\s+)?\"?credential_operations\b", re.IGNORECASE)

#: The one lawful deleter: (path, function).
ALLOWED = {("app/services/credential_lifecycle.py", "expire_stale_operations")}


@dataclass(frozen=True)
class Hit:
    path: str
    function: str
    line: int
    rule: str


def _names_operations(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id == MODEL:
            return True
        if isinstance(child, ast.Attribute) and child.attr == MODEL:
            return True
        if isinstance(child, ast.Constant) and isinstance(child.value, str) and child.value == TABLE:
            return True
    return False


def _is_delete_call(call: ast.Call) -> bool:
    func = call.func
    return (isinstance(func, ast.Attribute) and func.attr == "delete") or (
        isinstance(func, ast.Name) and func.id == "delete"
    )


def _tainted_names(function: ast.AST) -> set[str]:
    """Names in ``function`` bound (directly or through a loop) to something naming operation rows."""
    tainted: set[str] = set()

    def mentions(node: ast.AST) -> bool:
        return _names_operations(node) or any(
            isinstance(n, ast.Name) and n.id in tainted for n in ast.walk(node))

    for _ in range(3):  # a few passes settle ``ops = ...; for op in ops``
        for node in ast.walk(function):
            if isinstance(node, ast.Assign) and mentions(node.value):
                tainted.update(t.id for t in node.targets if isinstance(t, ast.Name))
            elif isinstance(node, (ast.For, ast.AsyncFor)) and mentions(node.iter):
                tainted.update(n.id for n in ast.walk(node.target) if isinstance(n, ast.Name))
            elif isinstance(node, ast.NamedExpr) and mentions(node.value):
                tainted.add(node.target.id)
    return tainted


def _root_name(node: ast.AST) -> str | None:
    while isinstance(node, (ast.Attribute, ast.Call, ast.Subscript)):
        node = node.func if isinstance(node, ast.Call) else node.value
    return node.id if isinstance(node, ast.Name) else None


def find_deletes(source: str, path: str = "<source>") -> list[Hit]:
    """Every place ``source`` may delete ``credential_operations`` rows, allowed or not."""
    tree = ast.parse(source)
    hits: list[Hit] = []

    def visit(node: ast.AST, function: str, tainted: set[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, child.name, _tainted_names(child))
                continue
            if isinstance(child, ast.Call) and _is_delete_call(child):
                if isinstance(child.func, ast.Attribute):
                    direct = _names_operations(child.func.value) or any(_names_operations(a) for a in child.args)
                    receiver = _root_name(child.func.value)
                    via_name = (receiver in tainted) or any(
                        isinstance(n, ast.Name) and n.id in tainted for a in child.args for n in ast.walk(a))
                else:
                    direct = any(_names_operations(a) for a in child.args)
                    via_name = any(isinstance(n, ast.Name) and n.id in tainted
                                   for a in child.args for n in ast.walk(a))
                if direct:
                    hits.append(Hit(path, function, child.lineno, "delete naming credential_operations"))
                elif via_name:
                    hits.append(Hit(path, function, child.lineno, "delete of an object bound to credential_operations"))
            if isinstance(child, ast.Constant) and isinstance(child.value, str) and _RAW_SQL.search(child.value):
                hits.append(Hit(path, function, child.lineno, "raw SQL delete of credential_operations"))
            visit(child, function, tainted)

    visit(tree, "<module>", set())
    return hits


def scan_repository(root) -> tuple[list[Hit], int]:
    """``(hits outside the allowed deleter, files parsed)`` under ``app/``."""
    hits: list[Hit] = []
    parsed = 0
    for file in sorted((root / "app").rglob("*.py")):
        if "__pycache__" in file.parts:
            continue
        rel = file.relative_to(root).as_posix()
        for hit in find_deletes(file.read_text(encoding="utf-8"), rel):
            if (hit.path, hit.function) not in ALLOWED:
                hits.append(hit)
        parsed += 1
    return hits, parsed
