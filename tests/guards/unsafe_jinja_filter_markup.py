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
The rule: a template expression may end in ``|safe`` only when every filter
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

_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)

# markupsafe.escape(...) / escape(...), and bleach's .clean(...) / bleach.clean(...).
# Named, not spelled against a single import style, so `from markupsafe import
# escape` and `from app.utils.encryption import escape as esc` are both still
# "a call named escape" by the receiver's own attribute/name.
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


def _calls_escape_or_sanitize(node: ast.AST) -> bool:
    for n in ast.walk(node):
        if not isinstance(n, ast.Call):
            continue
        func = n.func
        if isinstance(func, ast.Name) and func.id in _SAFE_CALL_NAMES:
            return True
        if isinstance(func, ast.Attribute) and func.attr in _SAFE_CALL_NAMES:
            return True
    return False


def _is_markup_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "Markup"
    if isinstance(func, ast.Attribute):
        return func.attr == "Markup"
    return False


def _assignments(nodes) -> list[tuple[set[str], ast.AST]]:
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
        names = {t.id for t in targets if isinstance(t, ast.Name)}
        if names:
            found.append((names, value))
    return found


def _all_names(node: ast.AST):
    """Every name referenced in ``node``, receivers of ``x.attr``/``x.method()``
    included — unlike PII-shape detection, a safety check cares whether the
    *base object* (e.g. ``escaped`` in ``escaped.replace(...)``) is safe, not
    just names used standalone."""
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            yield n.id


def _is_literal_text(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.JoinedStr):
        return not any(isinstance(part, ast.FormattedValue) for part in node.values)
    return False


def _is_provably_safe(value: ast.AST, safe_locals: set[str]) -> bool:
    """A value that cannot carry unescaped attacker/DB content into Markup()."""
    if _is_literal_text(value):
        return True
    if _calls_escape_or_sanitize(value):
        return True
    names = set(_all_names(value))
    return bool(names) and names <= safe_locals


def _to_fixpoint(bindings, rule) -> set[str]:
    found: set[str] = set()
    changed = True
    while changed:
        changed = False
        for names, value in bindings:
            if not names <= found and rule(value, found):
                found |= names
                changed = True
    return found


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
        scope_nodes = list(_walk_scope(node))
        safe_locals = _to_fixpoint(_assignments(scope_nodes), _is_provably_safe)
        for n in scope_nodes:
            if not _is_markup_call(n) or not n.args:
                continue
            arg = n.args[0]
            if _is_provably_safe(arg, safe_locals):
                continue
            violations.append(Violation(path, n.lineno, node.name, ast.unparse(n)[:160]))
    return sorted(violations, key=lambda v: v.line)


# ---------------------------------------------------------------------------
# Part B — Jinja templates
# ---------------------------------------------------------------------------

# Filters Part A's rule has proved escape before any Markup() they build is
# returned. Only a filter proved safe this way belongs here — this is an
# allowlist of filter *behavior*, not a list of names to trust on faith.
SAFE_BEFORE_SAFE_FILTERS = frozenset({"nl2br"})

_EXPR_RE = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)
_AUTOESCAPE_FALSE_RE = re.compile(r"\{%-?\s*autoescape\s+false\s*-?%\}")
_TRAILING_SAFE_RE = re.compile(r"\|\s*safe\s*$")


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
        if not _TRAILING_SAFE_RE.search(expr):
            continue
        before_safe = _TRAILING_SAFE_RE.sub("", expr).strip()
        segments = before_safe.split("|")
        filters_applied = [seg.strip().split("(", 1)[0].strip() for seg in segments[1:]]
        if filters_applied and set(filters_applied) <= allowlist:
            continue
        normalized = re.sub(r"\s+", "", before_safe)
        violations.append(
            TemplateViolation(
                path,
                _line_of(source, match.start()),
                "unsafe_safe_filter",
                match.group(0)[:160],
                key=f"{path}::{normalized}|safe",
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
