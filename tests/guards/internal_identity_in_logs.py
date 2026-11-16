"""Detection of log calls that would print an internal identity.

Factored out of the test so it can be fed a synthetic violation and proved to
report it (SOP-TEST-003 §IX.A).

The rule (DOM-OPS-001 §7, owner ruling 2026-10-27): `classes.class_id`,
`seats.id` and `users.id` stay inside the database. A log line names a class by
`class_public_id` and a seat by `seats.public_id`, and omits the authentication
principal. A composed idempotency key or correlation id can carry those
identities, so it is logged through `loggable_token`.

What counts as an internal identity here is an expression a log call's
arguments read: a name or attribute spelled like one (`class_id`, `seat_id`,
`user_id`, `student_id`, `target_seat_id`, ...), an `.id` / `.user_id` /
`.class_id` read on a seat, student, user, teacher or class object, the same
through `getattr(obj, "id")`, or a key read such as `ctx.get("class_id")` or
`row["seat_id"]`. Values passed through `class_log_ref`,
`seat_log_ref` or `loggable_token` are already public, and a comparison logs
only its truth value, so neither is reported.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

LOG_METHODS = frozenset({"debug", "info", "warning", "warn", "error", "exception", "critical", "log"})
# `len` logs only a length.
SAFE_WRAPPERS = frozenset({"class_log_ref", "seat_log_ref", "loggable_token", "len"})

_IDENTITY_NAME = re.compile(
    r"(^|_)(class|seat|user|student|teacher|actor|membership)_?ids?$"
)
_TOKEN_NAME = re.compile(r"(^|_)(correlation_id|idempotency_key)$")
_OWNER = re.compile(r"(seat|student|user|teacher|actor|class|classroom|klass|economy)", re.IGNORECASE)
_OWNER_ID_ATTRS = frozenset({"id", "user_id", "class_id"})


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    expression: str


def _is_log_call(node: ast.Call) -> bool:
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr in LOG_METHODS
        and "log" in ast.unparse(func.value).lower()
    )


def _identity_reads(node: ast.AST):
    if isinstance(node, ast.Call):
        func_name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
        if func_name in SAFE_WRAPPERS:
            return
        if func_name == "getattr" and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
            attr = node.args[1].value
            if isinstance(attr, str) and (
                _IDENTITY_NAME.search(attr)
                or (attr in _OWNER_ID_ATTRS and _OWNER.search(ast.unparse(node.args[0])))
            ):
                yield ast.unparse(node)
                return
        if (
            func_name == "get" and node.args and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str) and _IDENTITY_NAME.search(node.args[0].value)
        ):
            yield ast.unparse(node)
            return
    if (
        isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, str) and _IDENTITY_NAME.search(node.slice.value)
    ):
        yield ast.unparse(node)
        return
    if isinstance(node, ast.Compare):
        return
    if isinstance(node, (ast.GeneratorExp, ast.ListComp, ast.SetComp)):
        # Only the element is printed; the loop variable and source are not.
        yield from _identity_reads(node.elt)
        return
    if isinstance(node, ast.Name) and (_IDENTITY_NAME.search(node.id) or _TOKEN_NAME.search(node.id)):
        yield node.id
        return
    if isinstance(node, ast.Attribute):
        if _IDENTITY_NAME.search(node.attr) or _TOKEN_NAME.search(node.attr):
            yield ast.unparse(node)
            return
        if node.attr in _OWNER_ID_ATTRS and _OWNER.search(ast.unparse(node.value)):
            yield ast.unparse(node)
            return
    for child in ast.iter_child_nodes(node):
        yield from _identity_reads(child)


def find_violations(source: str, path: str = "<source>") -> list[Violation]:
    """Every log-call argument in ``source`` that reads an internal identity."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and _is_log_call(node)):
            continue
        arguments = list(node.args) + [keyword.value for keyword in node.keywords]
        for argument in arguments:
            for expression in _identity_reads(argument):
                found.append(Violation(path, node.lineno, expression))
    return found
