"""Detection of state-changing browser fetches that carry no CSRF token.

Factored out of the test so it can be fed a synthetic violation and proved to
report it (SOP-TEST-003 §IX.A). A guard that only ever runs over a compliant
tree cannot distinguish "no violation exists" from "the detector stopped
detecting".

The rule this enforces: a ``fetch`` that changes state must go through
``AppCore.csrfFetch``, which attaches ``X-CSRFToken``, or attach the header
itself within the same call. Flask-WTF rejects anything else with 400 before
the route runs, so an omission does not degrade — it disables the feature.

The application test suite cannot observe this defect at all: ``conftest.py``
sets ``WTF_CSRF_ENABLED=False``, so every request-level test passes with or
without the header. This source-level check is the only gate that can see it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Verbs that mutate state. GET/HEAD are exempt: Flask-WTF does not protect them
# and they carry no CSRF risk.
STATE_CHANGING = ("POST", "PUT", "PATCH", "DELETE")

# ``fetch(`` as a call, but never the tail of a longer identifier. JavaScript is
# case-sensitive, so ``csrfFetch(`` does not match this; the negative lookbehind
# additionally rejects ``myfetch(`` and ``.somefetch(``.
_FETCH_CALL = re.compile(r"(?<![A-Za-z0-9_$.])fetch\s*\(")

_METHOD = re.compile(
    r"""method\s*:\s*['"](%s)['"]""" % "|".join(STATE_CHANGING),
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    method: str
    excerpt: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line} — {self.method} via bare fetch(): {self.excerpt}"


def _call_arguments(source: str, open_paren_index: int) -> str | None:
    """The text between a call's parentheses, respecting nesting and strings.

    Returns None for an unbalanced call, which means the source is not something
    this detector can reason about; the caller treats that as "cannot assess"
    rather than silently as "compliant".
    """
    depth = 0
    i = open_paren_index
    quote: str | None = None
    n = len(source)
    while i < n:
        ch = source[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'`":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                return source[open_paren_index + 1: i]
        i += 1
    return None


def find_unprotected_state_changing_fetches(source: str, path: str = "<source>") -> list[Violation]:
    """Every bare ``fetch`` in ``source`` that mutates state without a CSRF token."""
    violations: list[Violation] = []

    for match in _FETCH_CALL.finditer(source):
        args = _call_arguments(source, match.end() - 1)
        if args is None:
            continue
        method_match = _METHOD.search(args)
        if not method_match:
            continue
        if "X-CSRFToken" in args:
            continue
        line = source.count("\n", 0, match.start()) + 1
        excerpt = " ".join(args.strip().split())[:100]
        violations.append(Violation(
            path=path,
            line=line,
            method=method_match.group(1).upper(),
            excerpt=excerpt,
        ))

    return violations
