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
``extra=`` — is reported, whatever the receiver is called.
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

# Bare locals that, by name, hold a name: ``full_name = profile.full_name`` one
# line above the call defeats an attribute-only check.
NAME_LOCALS = NAME_ATTRIBUTES

LOG_METHODS = frozenset({
    "debug", "info", "warning", "warn", "error", "exception", "critical", "fatal", "log",
})

# The receiver of a logging call: ``logger``, ``current_app.logger``,
# ``app.logger``, ``self._log``, ``logging``, ``logging.getLogger(__name__)``.
_LOGGER_NAME = re.compile(r"^_*(?:logger|log|logging|getlogger|app_logger)$", re.IGNORECASE)


def _receiver_name(node: ast.AST) -> str | None:
    """The last name segment of a call's receiver; ``getLogger`` for a getLogger() call."""
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    field: str
    excerpt: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line} — logs {self.field}: {self.excerpt}"


def is_logger_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr not in LOG_METHODS:
        return False
    name = _receiver_name(node.func.value)
    return bool(name and _LOGGER_NAME.match(name))


def _offending_field(node: ast.AST) -> str | None:
    if isinstance(node, ast.Attribute):
        if node.attr in NAME_ATTRIBUTES or node.attr in PROFILE_ATTRIBUTES:
            return node.attr
    if isinstance(node, ast.Name) and node.id in NAME_LOCALS:
        return node.id
    return None


def count_logger_calls(source: str) -> int:
    """How many logger calls the detector recognises — for the rename check."""
    return sum(1 for node in ast.walk(ast.parse(source)) if is_logger_call(node))


def find_pii_in_log_calls(source: str, path: str = "<source>") -> list[Violation]:
    violations: list[Violation] = []
    for node in ast.walk(ast.parse(source)):
        if not is_logger_call(node):
            continue
        arguments = [*node.args, *(kw.value for kw in node.keywords)]
        for argument in arguments:
            field = next(
                (f for sub in ast.walk(argument) if (f := _offending_field(sub))),
                None,
            )
            if field:
                violations.append(Violation(path, node.lineno, field, ast.unparse(node)[:160]))
                break
    return violations
