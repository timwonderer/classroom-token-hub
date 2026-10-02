"""Detection of a stored or hard-coded pay frequency in payroll code.

Operator ruling 2026-09-30: pay frequency is always derived from
``pay_schedule_type`` through the anchored recurrence (SPEC-TIME-001 §IX.12;
DOM-PROD-001 §XV.5), never stored and never approximated as a number of days —
"less chance of drift". The ``payroll_settings.payroll_frequency_days`` column
was dropped for that reason, and a month is not 30 days.

Factored out of the test so it can be fed synthetic violations and proved to
report them (SOP-TEST-003 §IX.A). It parses Python source and reports:

* anywhere in ``app/``: the identifier ``payroll_frequency_days`` as a name,
  attribute, keyword argument or string (a stored day count coming back);
* in payroll modules: a ``days=`` argument of 28–31 (a month approximated as
  days), and a dict mapping a schedule name (``weekly``, ``biweekly``,
  ``monthly``, ``daily``) to a number (a schedule approximated as days).
* anywhere in ``app/``: any use of ``rounding_mode``. Rounding is RETIRED
  (operator ruling 2026-09-30): it was never defined or applied, and the column
  survives only as historical data. The one allowed occurrence is the column's
  own declaration in ``app/models.py``.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

FORBIDDEN_NAME = "payroll_frequency_days"
RETIRED_ROUNDING = "rounding_mode"
MODELS_MODULE = "app/models.py"
MONTH_AS_DAYS = frozenset({28, 29, 30, 31})
SCHEDULE_NAMES = frozenset({"weekly", "biweekly", "monthly", "daily"})
PAYROLL_MODULES = (
    "app/services/payroll/",
    "app/feats/prod.py",
    "app/feats/complete_payroll_cycle.py",
    "app/utils/economy_balance.py",
)


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    reason: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line} — {self.reason}"


def _is_payroll_module(path: str) -> bool:
    path = path.replace("\\", "/")
    return any(path.startswith(prefix) or path.endswith(prefix) for prefix in PAYROLL_MODULES)


def _int_constant(node) -> int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return node.value
    return None


def find_violations(path: str, source: str) -> list[Violation]:
    tree = ast.parse(source)
    payroll = _is_payroll_module(path)
    found: dict[tuple[int, str], Violation] = {}

    def report(node, reason):
        line = getattr(node, "lineno", 0)
        found.setdefault((line, reason), Violation(path, line, reason))

    models = path.replace("\\", "/").endswith(MODELS_MODULE)
    rounding = "retired rounding setting (rounding_mode) used"
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == RETIRED_ROUNDING:
            # The column's declaration in the model is the only lawful mention.
            if not (models and isinstance(node.ctx, ast.Store)):
                report(node, rounding)
        elif isinstance(node, ast.Attribute) and node.attr == RETIRED_ROUNDING:
            report(node, rounding)
        elif isinstance(node, ast.keyword) and node.arg == RETIRED_ROUNDING:
            report(node.value, rounding)
        elif isinstance(node, ast.Constant) and node.value == RETIRED_ROUNDING:
            report(node, rounding)
        if isinstance(node, ast.Name) and node.id == FORBIDDEN_NAME:
            report(node, "stored pay frequency (payroll_frequency_days)")
        elif isinstance(node, ast.Attribute) and node.attr == FORBIDDEN_NAME:
            report(node, "stored pay frequency (payroll_frequency_days)")
        elif isinstance(node, ast.keyword) and node.arg == FORBIDDEN_NAME:
            report(node.value, "stored pay frequency (payroll_frequency_days)")
        elif isinstance(node, ast.Constant) and node.value == FORBIDDEN_NAME:
            report(node, "stored pay frequency (payroll_frequency_days)")
        if not payroll:
            continue
        if isinstance(node, ast.keyword) and node.arg == "days" and _int_constant(node.value) in MONTH_AS_DAYS:
            report(node.value, "a month approximated as a number of days")
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if (
                    isinstance(key, ast.Constant) and key.value in SCHEDULE_NAMES
                    and _int_constant(value) is not None
                ):
                    report(key, f"pay schedule {key.value!r} approximated as a number of days")
    return sorted(found.values(), key=lambda violation: violation.line)
