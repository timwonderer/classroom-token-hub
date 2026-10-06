"""Detection of forward-only Alembic revisions (SOP-DB-004 §V.5).

A revision is forward-only when its ``downgrade()`` raises, or does nothing for
the schema or data it changed. The definition is the revision's own
``downgrade()``, not a hand-kept list, so this reads it from source.

Factored out of the test so it can be fed synthetic revisions and proved to
report them (SOP-TEST-003 §IX.A). Rules:

* a ``raise`` anywhere in ``downgrade()`` counts, including one inside a
  conditional: a downgrade that refuses on some data is not reliably reversible;
* a call from ``downgrade()`` to a function in the same module that raises counts
  (one level, which is the shape ``a7e3c9d1f5b2`` uses);
* a ``downgrade()`` whose statements are all no-ops (``pass``, bare ``return``,
  a docstring or other constant, ``print``) counts;
* a pure merge revision (``down_revision`` is a tuple and ``upgrade()`` does
  nothing) is not forward-only: it changed nothing. A merge whose ``upgrade()``
  does work is judged like any other revision.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Revision:
    revision: str
    down_revision: object
    forward_only: bool
    reason: str


def _literal(tree: ast.Module, name: str):
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        for target in targets:
            if getattr(target, "id", None) == name and node.value is not None:
                return ast.literal_eval(node.value)
    return None


def _raises(node: ast.AST) -> bool:
    return any(isinstance(child, ast.Raise) for child in ast.walk(node))


def _is_noop_statement(stmt: ast.stmt) -> bool:
    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Return):
        return stmt.value is None or isinstance(stmt.value, ast.Constant)
    if isinstance(stmt, ast.Expr):
        value = stmt.value
        if isinstance(value, ast.Constant):
            return True
        if isinstance(value, ast.Call) and getattr(value.func, "id", None) == "print":
            return True
    return False


def _is_noop(func: ast.FunctionDef | None) -> bool:
    return func is None or all(_is_noop_statement(stmt) for stmt in func.body)


def classify_revision(source: str) -> Revision:
    """Classify one migration file's source. Pure."""
    tree = ast.parse(source)
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    revision = _literal(tree, "revision")
    down = _literal(tree, "down_revision")
    upgrade, downgrade = funcs.get("upgrade"), funcs.get("downgrade")

    if isinstance(down, (tuple, list)) and _is_noop(upgrade):
        return Revision(revision, down, False, "pure merge: changes nothing")
    if downgrade is None:
        return Revision(revision, down, True, "no downgrade()")
    if _raises(downgrade):
        return Revision(revision, down, True, "downgrade() raises")
    for call in ast.walk(downgrade):
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
            helper = funcs.get(call.func.id)
            if helper is not None and helper is not downgrade and _raises(helper):
                return Revision(revision, down, True, f"downgrade() calls {call.func.id}(), which raises")
    if _is_noop(downgrade):
        return Revision(revision, down, True, "downgrade() does nothing")
    return Revision(revision, down, False, "downgrade() does work")


def derive_forward_only(versions_dir: Path) -> dict[str, str]:
    """{revision: reason} for every forward-only revision under ``versions_dir``."""
    found: dict[str, str] = {}
    for path in sorted(Path(versions_dir).glob("*.py")):
        rev = classify_revision(path.read_text(encoding="utf-8"))
        if rev.forward_only:
            found[rev.revision] = rev.reason
    return found


def read_register(path: Path) -> set[str]:
    """Revision ids in the register file; ``#`` starts a comment."""
    ids = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            ids.add(line)
    return ids
