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
defined — filters are registered by reference
(``app.jinja_env.filters['name'] = some_function``), so the check is in two
passes: find every registered function *name* across the sources given, then
walk every function definition with that name.

Part B — Jinja templates
-------------------------
The rule: a template expression may contain ``|safe`` only when every filter
applied to it is on a small allowlist of filters Part A has already proved
escape before returning ``Markup()`` (today: ``nl2br``). A bare ``{{ x|safe
}}``, or ``|safe`` preceded only by filters not on that allowlist, is
reported. An ``{% autoescape false %}`` block is reported unconditionally —
there is no allowlist for turning off Jinja's own protection.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from jinja2 import Environment, nodes as jinja_nodes

_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)

# markupsafe.escape(...) / escape(...), and bleach's .clean(...) / bleach.clean(...).
# This is a name-based structural check, not import/provenance resolution.
_SAFE_CALL_NAMES = frozenset({"escape", "clean"})


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


def _is_provably_safe(value: ast.AST, safe_locals: set[str]) -> bool:
    """Prove the whole expression, not merely one sanitized descendant."""
    if isinstance(value, ast.Constant):
        return True
    if isinstance(value, ast.Name):
        return value.id in safe_locals
    if isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add):
        return all(_is_provably_safe(part, safe_locals) for part in (value.left, value.right))
    if isinstance(value, ast.JoinedStr):
        return all(
            _is_provably_safe(part.value if isinstance(part, ast.FormattedValue) else part, safe_locals)
            for part in value.values
        )
    if isinstance(value, ast.IfExp):
        return all(_is_provably_safe(part, safe_locals) for part in (value.body, value.orelse))
    if isinstance(value, ast.Call):
        func = value.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if name in _SAFE_CALL_NAMES:
            return True
        if isinstance(func, ast.Name) and name == "str" and len(value.args) == 1:
            return _is_provably_safe(value.args[0], safe_locals)
        if isinstance(func, ast.Attribute) and func.attr == "replace":
            return _is_provably_safe(func.value, safe_locals) and all(
                _is_provably_safe(arg, safe_locals)
                for arg in [*value.args, *(kw.value for kw in value.keywords)]
            )
    return False


def _written_names(node: ast.AST) -> set[str]:
    return {
        n.id for n in _walk_scope(node)
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del))
    }


def find_filter_registrations(source: str) -> set[str]:
    """Function names assigned as the value of a ``*.filters['x'] = fn`` subscript."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Name):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Attribute)
                and target.value.attr == "filters"
            ):
                names.add(node.value.id)
    return names


def find_unsafe_markup_in_filters(
    source: str, filter_names: set[str], path: str = "<source>"
) -> list[Violation]:
    tree = ast.parse(source)
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in filter_names:
            continue
        def inspect(expression, safe_locals):
            # Expression-level writes are not ordered by ast.walk; fail closed.
            safe_locals = safe_locals - _written_names(expression)
            for call in [expression, *_walk_scope(expression)]:
                if _is_markup_call(call) and call.args:
                    if not _is_provably_safe(call.args[0], safe_locals):
                        violations.append(
                            Violation(path, call.lineno, node.name, ast.unparse(call)[:160])
                        )

        def visit(statements, incoming):
            safe_locals = incoming.copy()
            for statement in statements:
                if isinstance(statement, ast.If):
                    inspect(statement.test, safe_locals)
                    safe_locals -= _written_names(statement.test)
                    safe_locals = visit(statement.body, safe_locals) & visit(statement.orelse, safe_locals)
                elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
                    value = statement.value
                    if value is not None:
                        inspect(value, safe_locals)
                        safe = _is_provably_safe(value, safe_locals - _written_names(value))
                    else:
                        safe = False
                    safe_locals -= _written_names(statement)
                    targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                    if safe:
                        safe_locals.update(t.id for t in targets if isinstance(t, ast.Name))
                else:
                    # shortcut: loops/try/with use conservative write invalidation;
                    # add control-flow modeling if a legitimate filter needs it.
                    safe_locals -= _written_names(statement)
                    inspect(statement, safe_locals)
            return safe_locals

        visit(node.body, set())
    return sorted(violations, key=lambda v: v.line)


# ---------------------------------------------------------------------------
# Part B — Jinja templates
# ---------------------------------------------------------------------------

# Filters Part A's rule has proved escape before any Markup() they build is
# returned. Only a filter proved safe this way belongs here — this is an
# allowlist of filter *behavior*, not a list of names to trust on faith.
SAFE_BEFORE_SAFE_FILTERS = frozenset({"nl2br"})

_EXPR_RE = re.compile(r"\{\{-?(.*?)-?\}\}", re.DOTALL)
_AUTOESCAPE_FALSE_RE = re.compile(r"\{%-?\s*autoescape\s+false\s*-?%\}")
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


def load_baseline(text: str) -> set[str]:
    """Parse the pre-existing-debt baseline (one ``path::expr`` key per
    non-comment line) — same convention as ``migrations/lint_baseline.txt``:
    frozen pre-gate debt that a PR may not add to, only shrink."""
    return {
        stripped
        for line in text.splitlines()
        if (stripped := line.split("#", 1)[0].strip())
    }


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
