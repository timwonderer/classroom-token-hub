"""Detection of logger calls that reach into a student's name.

Factored out of the test so it can be fed a synthetic violation and proved to
report it (SOP-TEST-003 §IX.A).

The rule this enforces: logs MUST NOT contain sensitive personal information
(INV-ARC-005 §V). Names live only in ``identity_profiles``, encrypted with
``PIIEncryptedType`` (INV-ARC-018), so the one way a name reaches a log line is
for a logger call to read it off the profile. Attribution uses seat and class
ids instead.

The check is on argument *shape*, not on likely variable names: any attribute
access to a name field, and any access through ``identity_profile``, anywhere
inside a logger call's arguments — f-string, ``%`` args, ``.format()``,
``extra=`` — is reported, whatever the receiver is called. Bindings are
resolved rather than spelled: a local assigned a name (directly or through
other locals) counts as a name, and a logger bound to any identifier
(``audit = logging.getLogger(...)``, ``log_fn = current_app.logger.warning``)
counts as a logger.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

# IdentityProfile's PII columns and the properties derived from them.
NAME_ATTRIBUTES = frozenset({"first_name", "last_name", "full_name", "last_initial"})

# Reaching through the profile at all — ``.notes`` is PII too, and the profile
# holds nothing else a log line needs.
PROFILE_ATTRIBUTES = frozenset({"identity_profile"})

# Bare locals that, by name, hold a name. Locals of any other name are tainted
# by what they are assigned from (see _Bindings).
NAME_LOCALS = NAME_ATTRIBUTES

LOG_METHODS = frozenset({
    "debug", "info", "warning", "warn", "error", "exception", "critical", "fatal", "log",
})

# The receiver of a logging call: ``logger``, ``current_app.logger``,
# ``app.logger``, ``self._log``, ``logging``, ``logging.getLogger(__name__)``.
_LOGGER_NAME = re.compile(r"^_*(?:logger|log|logging|getlogger|app_logger)$", re.IGNORECASE)


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    field: str
    excerpt: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line} — logs {self.field}: {self.excerpt}"


_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def _receiver_name(node: ast.AST) -> str | None:
    """The last name segment of a receiver; ``getLogger`` for a getLogger() call."""
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _walk_scope(scope: ast.AST):
    """Nodes of one scope, not descending into nested functions."""
    stack = list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, _SCOPES):
            stack.extend(ast.iter_child_nodes(node))


def _assignments(nodes) -> list[tuple[set[str], ast.AST]]:
    """(target names, value) for every simple binding among ``nodes``."""
    found = []
    for node in nodes:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and node.value is not None:
            targets, value = [node.target], node.value
        elif isinstance(node, ast.NamedExpr):
            targets, value = [node.target], node.value
        else:
            continue
        names = {_receiver_name(t) for t in targets if isinstance(t, (ast.Name, ast.Attribute))}
        names.discard(None)
        if names:
            found.append((names, value))
    return found


def _whole_names(node: ast.AST):
    """Names used as values in their own right — not as the receiver of ``x.attr``."""
    receivers = {id(n.value) for n in ast.walk(node) if isinstance(n, ast.Attribute)}
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and id(n) not in receivers:
            yield n.id


def _to_fixpoint(bindings, rule) -> set[str]:
    """Names bound by ``bindings`` whose value satisfies ``rule(value, found_so_far)``."""
    found: set[str] = set()
    changed = True
    while changed:
        changed = False
        for names, value in bindings:
            if not names <= found and rule(value, found):
                found |= names
                changed = True
    return found


def _is_logger_expr(node: ast.AST, loggers: set[str]) -> bool:
    if isinstance(node, ast.Call) and _receiver_name(node) == "getLogger":
        return True
    name = _receiver_name(node) if isinstance(node, (ast.Name, ast.Attribute)) else None
    return bool(name and (_LOGGER_NAME.match(name) or name in loggers))


def _is_log_method(node: ast.AST, loggers: set[str]) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr in LOG_METHODS
        and _is_logger_expr(node.value, loggers)
    )


def _binds_logger(value: ast.AST, loggers: set[str]) -> bool:
    parts = list(ast.walk(value))
    if any(isinstance(n, ast.Attribute) and n.attr in LOG_METHODS for n in parts):
        return False  # a bound method, not a logger
    return any(_is_logger_expr(n, loggers) for n in parts)


def _carries_a_name(value: ast.AST, tainted: set[str]) -> bool:
    if any(isinstance(n, ast.Attribute) and n.attr in NAME_ATTRIBUTES for n in ast.walk(value)):
        return True
    return any(name in tainted | NAME_LOCALS for name in _whole_names(value))


def _offending_field(argument: ast.AST, tainted: set[str]) -> str | None:
    for node in ast.walk(argument):
        if isinstance(node, ast.Attribute) and (
            node.attr in NAME_ATTRIBUTES or node.attr in PROFILE_ATTRIBUTES
        ):
            return node.attr
    for name in _whole_names(argument):
        if name in tainted or name in NAME_LOCALS:
            return name
    return None


class _Module:
    """Logger bindings (module-wide) and name-carrying locals (per function).

    A logger is usually bound once at module level, so logger aliases resolve
    across the module. Taint does not: in an 11,000-line route module the same
    local is rebound in hundreds of functions, so a name-carrying local is
    tracked only inside the function that binds it.
    """

    def __init__(self, source: str):
        self.tree = ast.parse(source)
        bindings = _assignments(ast.walk(self.tree))
        self.loggers = _to_fixpoint(bindings, _binds_logger)
        self.log_methods = _to_fixpoint(
            bindings,
            lambda value, _: any(_is_log_method(n, self.loggers) for n in ast.walk(value)),
        )

    def is_logger_call(self, node: ast.AST) -> bool:
        if not isinstance(node, ast.Call):
            return False
        if _is_log_method(node.func, self.loggers):
            return True
        return isinstance(node.func, ast.Name) and node.func.id in self.log_methods

    def scopes(self):
        """(nodes of each scope, the locals in it that carry a name)."""
        for scope in [self.tree, *(n for n in ast.walk(self.tree) if isinstance(n, _SCOPES))]:
            nodes = list(_walk_scope(scope))
            yield nodes, _to_fixpoint(_assignments(nodes), _carries_a_name)


def count_logger_calls(source: str) -> int:
    """How many logger calls the detector recognises — for the rename check."""
    module = _Module(source)
    return sum(1 for node in ast.walk(module.tree) if module.is_logger_call(node))


def find_pii_in_log_calls(source: str, path: str = "<source>") -> list[Violation]:
    module = _Module(source)
    violations: list[Violation] = []
    for nodes, tainted in module.scopes():
        for node in nodes:
            if not module.is_logger_call(node):
                continue
            for argument in [*node.args, *(kw.value for kw in node.keywords)]:
                field = _offending_field(argument, tainted)
                if field:
                    violations.append(Violation(path, node.lineno, field, ast.unparse(node)[:160]))
                    break
    return sorted(violations, key=lambda v: v.line)
