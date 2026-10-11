"""Detection of the Markup()/|safe XSS taint shape neither CodeQL suite models.

Factored out of the test so each half can be fed a synthetic violation and
proved to report it (SOP-TEST-003 §IX.A). Written as the required follow-up
to ``docs/ops/audits/INCIDENT_2026-10-11_SEC-SAST-GAP-001.md`` §5: neither
CodeQL's default suite nor ``security-extended`` has a query for a function
registered into ``jinja_env.filters[...]`` that calls ``Markup()`` without
escaping first, or for ``|safe``-filtered template output built from
request- or database-sourced text — which is exactly how S4 shipped and how
one of S1's two sinks could have shipped.

Part A — Python filter functions
---------------------------------
The rule: a Jinja filter function may call ``Markup(x)`` only when ``x``
cannot carry unescaped attacker- or database-sourced text — a string
literal, a value that has already passed through
``markupsafe.escape(...)`` or a bleach ``.clean(...)``/``bleach.clean(...)``
call on this same value, or a reference built only from such values. Anything
else is reported, whatever the filter is named and wherever in ``app/`` it is
defined in the application or status service — filters are registered by reference
(``app.jinja_env.filters['name'] = some_function``), so the check is in two
passes: find every registered function *name* across the sources given, then
walk every function definition with that name.

Part B — Jinja templates
-------------------------
The rule: a template expression may contain ``|safe`` only when every filter
preceding it is on a small allowlist of filters Part A has already proved
escape before returning ``Markup()`` (today: ``nl2br``). A bare ``{{ x|safe
}}``, or ``|safe`` preceded only by filters not on that allowlist, is
reported. An ``{% autoescape false %}`` block is reported unconditionally —
there is no allowlist for turning off Jinja's own protection.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from dataclasses import dataclass

from jinja2 import Environment, nodes as jinja_nodes

_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)

_SANITIZERS = frozenset({"markupsafe.escape", "bleach.clean", "bleach.Cleaner().clean"})


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    filter_name: str
    excerpt: str

    def __str__(self) -> str:
        return (
            f"{self.path}:{self.line} — jinja filter {self.filter_name!r} wraps "
            f"unescaped content in Markup(): {self.excerpt}"
        )


def _walk_scope(scope: ast.AST):
    """Nodes of one scope, not descending into nested functions."""
    stack = list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, _SCOPES):
            stack.extend(ast.iter_child_nodes(node))


def _is_markup_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "Markup"
    if isinstance(func, ast.Attribute):
        return func.attr == "Markup"
    return False


def _provenance(value: ast.AST, bindings: dict[str, str]) -> str | None:
    if isinstance(value, ast.Name):
        return bindings.get(value.id)
    if isinstance(value, ast.Attribute):
        receiver = _provenance(value.value, bindings)
        return f"{receiver}.{value.attr}" if receiver else None
    if isinstance(value, ast.Call) and _provenance(value.func, bindings) == "bleach.Cleaner":
        return "bleach.Cleaner()"
    return None


def _import_bindings(node: ast.AST) -> dict[str, str]:
    if isinstance(node, ast.Import):
        return {a.asname or a.name.split(".")[0]: a.name if a.asname else a.name.split(".")[0]
                for a in node.names}
    if isinstance(node, ast.ImportFrom) and node.module and not node.level:
        return {a.asname or a.name: f"{node.module}.{a.name}" for a in node.names}
    return {}


def _is_provably_safe(value: ast.AST, safe_locals: set[str], bindings: dict[str, str]) -> bool:
    """Prove the whole expression, not merely one sanitized descendant."""
    if isinstance(value, ast.Constant):
        return True
    if isinstance(value, ast.Name):
        return value.id in safe_locals
    if isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add):
        return all(_is_provably_safe(part, safe_locals, bindings) for part in (value.left, value.right))
    if isinstance(value, ast.JoinedStr):
        return all(
            _is_provably_safe(part.value if isinstance(part, ast.FormattedValue) else part, safe_locals, bindings)
            for part in value.values
        )
    if isinstance(value, ast.IfExp):
        return all(_is_provably_safe(part, safe_locals, bindings) for part in (value.body, value.orelse))
    if isinstance(value, ast.Call):
        func = value.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if _provenance(func, bindings) in _SANITIZERS:
            return True
        if isinstance(func, ast.Name) and name == "str" and len(value.args) == 1:
            return _is_provably_safe(value.args[0], safe_locals, bindings)
        if isinstance(func, ast.Attribute) and func.attr == "replace":
            return _is_provably_safe(func.value, safe_locals, bindings) and all(
                _is_provably_safe(arg, safe_locals, bindings)
                for arg in [*value.args, *(kw.value for kw in value.keywords)]
            )
    return False


def _written_names(node: ast.AST) -> set[str]:
    names = set()
    for n in [node, *_walk_scope(node)]:
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            names.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            names.update(a.asname or a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.Attribute) and isinstance(n.ctx, (ast.Store, ast.Del)):
            base = n.value
            while isinstance(base, ast.Attribute):
                base = base.value
            if isinstance(base, ast.Name):
                names.add(base.id)
    return names


def find_filter_registrations(source: str) -> set[str]:
    """Discover direct assignments, literal updates, and Flask filter decorators.

    Unsupported registration values fail the guard instead of silently skipping.
    """
    names: set[str] = set()

    def register(value):
        if isinstance(value, ast.Name):
            names.add(value.id)
        elif isinstance(value, ast.Attribute):
            names.add(value.attr)
        else:
            raise ValueError(f"unsupported Jinja filter registration at line {value.lineno}")

    def is_filters(value):
        return isinstance(value, ast.Attribute) and value.attr == "filters"

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Subscript) and is_filters(t.value) for t in targets):
                if node.value is None:
                    raise ValueError(f"unsupported Jinja filter registration at line {node.lineno}")
                register(node.value)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "update" and is_filters(node.func.value):
                for arg in node.args:
                    if not isinstance(arg, ast.Dict) or any(key is None for key in arg.keys):
                        raise ValueError(f"unsupported Jinja filters.update at line {node.lineno}")
                    for value in arg.values:
                        register(value)
                for keyword in node.keywords:
                    if keyword.arg is None:
                        raise ValueError(f"unsupported Jinja filters.update at line {node.lineno}")
                    register(keyword.value)
            elif node.func.attr == "add_template_filter":
                value = node.args[0] if node.args else next(
                    (k.value for k in node.keywords if k.arg == "f"), None
                )
                if value is None:
                    raise ValueError(f"unsupported add_template_filter at line {node.lineno}")
                register(value)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                func = decorator.func if isinstance(decorator, ast.Call) else decorator
                if isinstance(func, ast.Attribute) and func.attr == "template_filter":
                    names.add(node.name)
    return names


def find_unsafe_markup_in_filters(
    source: str, filter_names: set[str], path: str = "<source>"
) -> list[Violation]:
    tree = ast.parse(source)
    violations: list[Violation] = []
    module_bindings: dict[str, str] = {}
    for statement in tree.body:
        if isinstance(statement, (ast.Import, ast.ImportFrom)):
            for name in _written_names(statement):
                module_bindings.pop(name, None)
            module_bindings.update(_import_bindings(statement))
        elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            module_bindings.pop(statement.name, None)
        else:
            for name in _written_names(statement):
                module_bindings.pop(name, None)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in filter_names:
            continue
        def inspect(expression, safe_locals, bindings):
            # Expression-level writes are not ordered by ast.walk; fail closed.
            writes = _written_names(expression)
            safe_locals = safe_locals - writes
            bindings = {k: v for k, v in bindings.items() if k not in writes}
            for call in [expression, *_walk_scope(expression)]:
                if not _is_markup_call(call):
                    continue
                arg = call.args[0] if call.args else next(
                    (kw.value for kw in call.keywords if kw.arg == "object"), None
                )
                unknown_args = any(isinstance(a, ast.Starred) for a in call.args) or any(
                    kw.arg is None for kw in call.keywords
                )
                if unknown_args or (arg is not None and not _is_provably_safe(arg, safe_locals, bindings)):
                    violations.append(Violation(path, call.lineno, node.name, ast.unparse(call)[:160]))

        def visit(statements, incoming, incoming_bindings):
            safe_locals = incoming.copy()
            bindings = incoming_bindings.copy()
            for statement in statements:
                writes = _written_names(statement)
                if isinstance(statement, ast.If):
                    inspect(statement.test, safe_locals, bindings)
                    test_writes = _written_names(statement.test)
                    safe_locals -= test_writes
                    bindings = {k: v for k, v in bindings.items() if k not in test_writes}
                    left_safe, left_bindings = visit(statement.body, safe_locals, bindings)
                    right_safe, right_bindings = visit(statement.orelse, safe_locals, bindings)
                    safe_locals = left_safe & right_safe
                    bindings = {k: v for k, v in left_bindings.items() if right_bindings.get(k) == v}
                elif isinstance(statement, (ast.Import, ast.ImportFrom)):
                    safe_locals -= writes
                    bindings = {k: v for k, v in bindings.items() if k not in writes}
                    bindings.update(_import_bindings(statement))
                elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
                    value = statement.value
                    value_bindings = {k: v for k, v in bindings.items() if k not in _written_names(value)} if value else {}
                    if value is not None:
                        inspect(value, safe_locals, bindings)
                        safe = _is_provably_safe(value, safe_locals - _written_names(value), value_bindings)
                        origin = _provenance(value, value_bindings)
                    else:
                        safe, origin = False, None
                    safe_locals -= writes
                    bindings = {k: v for k, v in bindings.items() if k not in writes}
                    targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                    for target in targets:
                        if isinstance(target, ast.Name):
                            if safe:
                                safe_locals.add(target.id)
                            if origin:
                                bindings[target.id] = origin
                else:
                    # shortcut: loops/try/with use conservative write invalidation;
                    # add control-flow modeling if a legitimate filter needs it.
                    safe_locals -= writes
                    bindings = {k: v for k, v in bindings.items() if k not in writes}
                    inspect(statement, safe_locals, bindings)
            return safe_locals, bindings

        parameters = {a.arg for a in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]}
        parameters.update(a.arg for a in (node.args.vararg, node.args.kwarg) if a)
        visit(node.body, set(), {k: v for k, v in module_bindings.items() if k not in parameters})
    return sorted(violations, key=lambda v: v.line)


# ---------------------------------------------------------------------------
# Part B — Jinja templates
# ---------------------------------------------------------------------------

# Filters Part A's rule has proved escape before any Markup() they build is
# returned. Only a filter proved safe this way belongs here — this is an
# allowlist of filter *behavior*, not a list of names to trust on faith.
SAFE_BEFORE_SAFE_FILTERS = frozenset({"nl2br"})

_EXPR_RE = re.compile(r"\{\{-?(.*?)-?\}\}", re.DOTALL)
_AUTOESCAPE_FALSE_RE = re.compile(r"\{%-?\s*autoescape\s+(?:false|False)\s*-?%\}")
_JINJA = Environment(autoescape=True)


@dataclass(frozen=True)
class TemplateViolation:
    path: str
    line: int
    kind: str  # "unsafe_safe_filter" | "autoescape_false"
    excerpt: str
    # Stable identity for the pre-existing-debt baseline below: None for
    # autoescape_false, which is never baseline-eligible. Line numbers drift
    # with unrelated edits, so the key is path + the normalized expression,
    # not path + line.
    key: str | None = None

    def __str__(self) -> str:
        if self.kind == "autoescape_false":
            return f"{self.path}:{self.line} — {{% autoescape false %}} disables Jinja's escaping"
        return (
            f"{self.path}:{self.line} — |safe on an expression not provably "
            f"pre-escaped: {self.excerpt}"
        )


def _line_of(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def find_unsafe_safe_filters(
    source: str, path: str = "<template>", allowlist: frozenset[str] = SAFE_BEFORE_SAFE_FILTERS
) -> list[TemplateViolation]:
    violations: list[TemplateViolation] = []
    for match in _EXPR_RE.finditer(source):
        expr = match.group(1).strip()
        parsed = _JINJA.parse(match.group(0))
        safe_filters = [n for n in parsed.find_all(jinja_nodes.Filter) if n.name == "safe"]
        if not safe_filters:
            continue
        for safe_filter in safe_filters:
            preceding = []
            value = safe_filter.node
            while isinstance(value, jinja_nodes.Filter):
                preceding.append(value.name)
                value = value.node
            if not preceding or not set(preceding) <= allowlist:
                break
        else:
            continue
        # Keep the existing baseline keys for ordinary trailing |safe usages.
        normalized = re.sub(r"\s+", "", expr)
        violations.append(
            TemplateViolation(
                path,
                _line_of(source, match.start()),
                "unsafe_safe_filter",
                match.group(0)[:160],
                key=f"{path}::{normalized}",
            )
        )
    return sorted(violations, key=lambda v: v.line)


def load_baseline(text: str) -> Counter[str]:
    """Parse one ``path::expr`` line per reviewed occurrence — like ``migrations/lint_baseline.txt``:
    frozen pre-gate debt that a PR may not add to, only shrink."""
    return Counter(
        stripped
        for line in text.splitlines()
        if (stripped := line.split("#", 1)[0].strip())
    )


def unbaselined_violations(violations: list[TemplateViolation], baseline: Counter[str]) -> list[TemplateViolation]:
    """Consume one reviewed baseline occurrence per matching sink."""
    remaining = baseline.copy()
    unrouted = []
    for violation in violations:
        if violation.key is not None and remaining[violation.key] > 0:
            remaining[violation.key] -= 1
        else:
            unrouted.append(violation)
    return unrouted


def find_autoescape_false_blocks(source: str, path: str = "<template>") -> list[TemplateViolation]:
    return sorted(
        (
            TemplateViolation(path, _line_of(source, m.start()), "autoescape_false", m.group(0))
            for m in _AUTOESCAPE_FALSE_RE.finditer(source)
        ),
        key=lambda v: v.line,
    )


def find_template_violations(source: str, path: str = "<template>") -> list[TemplateViolation]:
    return sorted(
        find_unsafe_safe_filters(source, path) + find_autoescape_false_blocks(source, path),
        key=lambda v: v.line,
    )
