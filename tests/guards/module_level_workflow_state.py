"""Detection of process-local mutable state in ``app/``.

Incident 2026-10-01: pending hall-pass requests lived in a module-level dict
(``_PENDING_REQUESTS``) that request handlers wrote to. That is one copy per
gunicorn worker. When production went from one worker to two, a request
enqueued by one worker was invisible to the other, and teachers' Approve and
Reject failed about half the time. Every worker must see the same workflow
state, so it belongs in the database (pending hall-pass requests are now
``pending_actions`` rows) or another store shared by all workers — never in a
module global.

Factored out of the test so it can be fed a synthetic violation and proved to
report it (SOP-TEST-003 §IX.A). It parses Python source and reports a
module-level name bound to a mutable container — a ``{}``/``[]``/``{x}``
literal or comprehension, or a call to ``dict``/``list``/``set``/
``defaultdict``/``OrderedDict``/``deque``/``Counter`` and friends — that any
function or method in the same module then mutates:

* item assignment, augmented item assignment or ``del`` (``NAME[k] = v``);
* a mutating method (``NAME.pop(k)``, ``NAME.setdefault(...)``,
  ``NAME[k].append(v)``, ``NAME.__setitem__``);
* the same through a local alias (``store = NAME; store[k] = v``);
* rebinding it under ``global NAME``.

A container that is only built at import time and read afterwards is a
constant and is not reported. A module whose mutation is lawful — a cache of a
pure function, a registry filled once at import — is named in ``ALLOWLIST``
with its reason.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

# (module path, name) -> why process-local mutation is lawful there. Keep it
# small: anything a request handler writes and another request must read is
# workflow state and does not belong here.
ALLOWLIST: dict[tuple[str, str], str] = {
    ("app/routes/admin.py", "_table_names_cache"):
        "schema introspection memo keyed by database URL; the schema is fixed for "
        "the life of the process, so every worker computes the same value",
    ("app/routes/admin.py", "_table_columns_cache"):
        "schema introspection memo keyed by (database URL, table); same reason",
    ("app/services/payroll/corrections.py", "_pending_cache"):
        "derived read memo keyed by the class's correction count with a 300 s TTL; "
        "a stale entry is impossible after an approval because the key changes, "
        "and every worker recomputes from the database",
}

_CONTAINER_CALLS = frozenset({
    "dict", "list", "set", "bytearray",
    "defaultdict", "OrderedDict", "deque", "Counter", "ChainMap",
    "WeakValueDictionary", "WeakKeyDictionary", "WeakSet",
})

_MUTATORS = frozenset({
    "append", "extend", "insert", "pop", "popitem", "remove", "clear", "update",
    "setdefault", "add", "discard", "sort", "reverse",
    "appendleft", "popleft", "extendleft", "rotate",
    "difference_update", "intersection_update", "symmetric_difference_update",
    "__setitem__", "__delitem__", "__ior__",
})


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    name: str
    excerpt: str

    def __str__(self) -> str:
        return (
            f"{self.path}:{self.line} — module-level mutable `{self.name}` is mutated "
            f"in a function (process-local state; persist it where every worker sees it): {self.excerpt}"
        )


def _is_container(value: ast.AST | None) -> bool:
    if isinstance(value, (ast.Dict, ast.List, ast.Set, ast.DictComp, ast.ListComp, ast.SetComp)):
        return True
    if isinstance(value, ast.Call):
        func = value.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
        return name in _CONTAINER_CALLS
    return False


def _module_statements(tree: ast.Module):
    """Top-level statements, descending into module-level if/try/with blocks."""
    pending = list(tree.body)
    while pending:
        node = pending.pop(0)
        yield node
        if isinstance(node, (ast.If, ast.Try, ast.With)):
            for field in ("body", "orelse", "finalbody", "handlers"):
                for child in getattr(node, field, []) or []:
                    if isinstance(child, ast.ExceptHandler):
                        pending.extend(child.body)
                    else:
                        pending.append(child)


def _module_containers(tree: ast.Module) -> dict[str, int]:
    names: dict[str, int] = {}
    for node in _module_statements(tree):
        if isinstance(node, ast.Assign) and _is_container(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.setdefault(target.id, node.lineno)
        elif isinstance(node, ast.AnnAssign) and _is_container(node.value):
            if isinstance(node.target, ast.Name):
                names.setdefault(node.target.id, node.lineno)
    return names


def _root_name(node: ast.AST) -> str | None:
    """``NAME``, ``NAME[k]``, ``NAME[k][j]`` -> ``NAME``."""
    while isinstance(node, ast.Subscript):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def _scope_nodes(scope: ast.AST):
    """Nodes of one lexical scope, not descending into nested functions or classes.

    ``ast.walk`` would include nested function bodies, whose bindings belong to
    their own scope (CodeRabbit on #1462). A nested scope node itself is yielded,
    so the caller can analyse it separately; its defaults and decorators belong
    to the enclosing scope and are yielded too.
    """
    if isinstance(scope, ast.Lambda):
        pending = [scope.body]
    else:
        pending = list(scope.body)
    while pending:
        node = pending.pop(0)
        yield node
        if isinstance(node, _SCOPES):
            if not isinstance(node, ast.ClassDef):
                pending.extend(d for d in node.args.defaults + node.args.kw_defaults if d is not None)
            pending.extend(getattr(node, "decorator_list", []))
            continue
        pending.extend(ast.iter_child_nodes(node))


def _scope_mutations(scope: ast.AST, containers: set[str], enclosing: dict[str, str | None]):
    """Mutations of module containers in one function scope, then its nested ones.

    ``enclosing`` maps each name visible from enclosing *function* scopes to what
    it refers to there: the module container's name (an alias, or the container
    itself), or ``None`` for a local that shadows it.
    """
    nodes = list(_scope_nodes(scope))
    declared_global: set[str] = set()
    declared_nonlocal: set[str] = set()
    for node in nodes:
        if isinstance(node, ast.Global):
            declared_global.update(node.names)
        elif isinstance(node, ast.Nonlocal):
            declared_nonlocal.update(node.names)

    # Names this function binds itself: parameters and assignment targets.
    local: set[str] = set()
    if not isinstance(scope, ast.ClassDef):
        args = scope.args
        for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg]:
            if arg is not None:
                local.add(arg.arg)
    for node in nodes:
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            local.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            local.add(node.name)
    local -= declared_global | declared_nonlocal

    def source(name: str | None) -> str | None:
        """The module container a *read* of ``name`` reaches, before aliases here."""
        if name is None:
            return None
        if name in declared_global:
            return name if name in containers else None
        if name in local:
            return None
        if name in enclosing:
            return enclosing[name]
        return name if name in containers else None

    # An alias is recorded only when its source resolves to the module container
    # (CodeRabbit on #1462): a parameter or local of the same name is not it.
    aliases: dict[str, str] = {}
    for node in nodes:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name):
            value = node.value.id
            target_container = aliases.get(value) or source(value)
            if target_container:
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id not in declared_global:
                        aliases[target.id] = target_container

    def resolve(name: str | None) -> str | None:
        if name in aliases:
            return aliases[name]
        return source(name)

    # A class body runs once, at import; only its methods run per request.
    for node in ([] if isinstance(scope, ast.ClassDef) else nodes):
        targets: list[ast.AST] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            targets = [node.target]
        elif isinstance(node, ast.Delete):
            targets = list(node.targets)
        for target in targets:
            if isinstance(target, ast.Subscript):
                name = resolve(_root_name(target))
                if name:
                    yield name, node
            elif isinstance(target, ast.Name) and target.id in containers and target.id in declared_global:
                yield target.id, node
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _MUTATORS:
            name = resolve(_root_name(node.func.value))
            if name:
                yield name, node

    # What this scope's names mean to the functions nested in it.
    inner = dict(enclosing)  # a class body is not an enclosing scope for its methods
    if not isinstance(scope, ast.ClassDef):
        for name in local:
            inner[name] = aliases.get(name)
        for name in declared_global:
            inner.pop(name, None)
    for node in nodes:
        if isinstance(node, _SCOPES):
            yield from _scope_mutations(node, containers, inner)


def _module_mutations(tree: ast.Module, containers: set[str]):
    """Every function and class at module level (and nested), each in its own scope."""
    for node in _scope_nodes(tree):
        if isinstance(node, _SCOPES):
            yield from _scope_mutations(node, containers, {})


def find_violations(path: str, source: str) -> list[Violation]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    containers = _module_containers(tree)
    if not containers:
        return []
    lines = source.splitlines()
    found: dict[tuple[str, int], Violation] = {}
    for name, node in _module_mutations(tree, set(containers)):
        if (path, name) in ALLOWLIST:
            continue
        excerpt = lines[node.lineno - 1].strip() if 0 < node.lineno <= len(lines) else ""
        found.setdefault((name, node.lineno), Violation(path, node.lineno, name, excerpt))
    return sorted(found.values(), key=lambda v: (v.line, v.name))
