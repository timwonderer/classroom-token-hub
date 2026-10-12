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
* a ``downgrade()`` that cannot change the schema or data counts: it makes no
  ``op.*`` or ``.execute`` call, directly or through same-module helpers, however
  it is dressed (``pass``, ``return``, ``print``, logging, an ``if`` around either);
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


def _does_work(func: ast.FunctionDef | None, funcs: dict, _seen: frozenset = frozenset()) -> bool:
    """True when ``func`` can change the schema or data.

    Positively identified, not guessed from a whitelist of no-op statements, so
    control flow around a ``print`` or ``logger.warning`` does not hide a no-op
    and a helper that only logs does not count as work. Work is: an ``op.*``
    call, any ``.execute(...)`` call, a call to a same-module function that does
    work (followed transitively), or a call to any other plain name that is not
    ``print`` (an imported helper is assumed to do work).
    """
    if func is None or func.name in _seen:
        return False
    seen = _seen | {func.name}
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        if isinstance(target, ast.Attribute):
            if getattr(target.value, "id", None) == "op" or target.attr in ("execute", "exec_driver_sql"):
                return True
        elif isinstance(target, ast.Name):
            if target.id in funcs:
                if _does_work(funcs[target.id], funcs, seen):
                    return True
            elif target.id != "print":
                return True
    return False


def classify_revision(source: str) -> Revision:
    """Classify one migration file's source. Pure."""
    tree = ast.parse(source)
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    revision = _literal(tree, "revision")
    down = _literal(tree, "down_revision")
    upgrade, downgrade = funcs.get("upgrade"), funcs.get("downgrade")

    if isinstance(down, (tuple, list)) and not _does_work(upgrade, funcs):
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
    if not _does_work(downgrade, funcs):
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
