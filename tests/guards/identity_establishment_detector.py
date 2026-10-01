"""Detection of views that touch identity-establishment state.

Factored out of the guard test so it can be fed a synthetic violation and
proved to report it (SOP-TEST-003 §IX.A).

The rule this enforces (DOM-IDEN-005 §VII, operator ruling 2026-10-01): claim,
credential setup and recovery setup require that no principal is signed in.
That is enforced by one gate keyed on a declared endpoint set
(``app/routes/identity_establishment.py``). The gate is only as complete as the
declaration, so any view that touches establishment state must be declared.

A function *touches* establishment state when its body

- uses the setup store (``student_setup.<anything>``, or a name imported from
  ``app.services.student_setup``) for anything but discarding a record
  (``discard``, ``forget_owner``), which deletion and unclaim must stay free to do;
- references FEAT-IDEN-001 ``resolve_seat_claim`` or FEAT-IDEN-002
  ``activate_student_credentials``;
- uses an onboarding session key in any way except ``session.pop(key, ...)``,
  which only discards it (sign-in clears these keys, and must stay free to); or
- calls, directly or through other functions, a function that touches it.

Calls are followed within a module and across ``from app... import name``,
which is how ``recovery.py`` reaches the setup helpers in ``student.py``.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

ONBOARDING_KEYS = frozenset({
    'onboarding_seat_ref',
    'onboarding_user_ref',
    'onboarding_claim_generation',
    'recovery_setup_authorization',
    'student_setup_token',
})
ESTABLISHMENT_COMMANDS = frozenset({'resolve_seat_claim', 'activate_student_credentials'})
SETUP_STORE = 'student_setup'
SETUP_STORE_CLEANUP = frozenset({'discard', 'forget_owner'})


@dataclass
class _Module:
    functions: dict[str, list[ast.AST]] = field(default_factory=dict)
    imported: dict[str, tuple[str, str]] = field(default_factory=dict)  # local name -> (module, name)
    key_aliases: set[str] = field(default_factory=set)


def _is_session_pop_of_key(node: ast.Call) -> bool:
    func = node.func
    return (isinstance(func, ast.Attribute) and func.attr == 'pop'
            and isinstance(func.value, ast.Name) and func.value.id == 'session')


def _index(source: str) -> _Module:
    tree = ast.parse(source)
    module = _Module()
    for node in tree.body:
        # ``SEAT_REF = 'onboarding_seat_ref'`` at module level, then ``session[SEAT_REF]``.
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and node.value.value in ONBOARDING_KEYS:
            module.key_aliases.update(t.id for t in node.targets if isinstance(t, ast.Name))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            module.functions.setdefault(node.name, []).append(node)
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith('app'):
            for alias in node.names:
                module.imported[alias.asname or alias.name] = (node.module, alias.name)
    return module


def _direct(function: ast.AST, module: _Module) -> tuple[set[str], set[str]]:
    """(reasons this body touches state itself, names it calls)."""
    reasons, calls = set(), set()
    nodes = [n for stmt in function.body for n in ast.walk(stmt)]
    lawful = set()  # ids of nodes that only discard: session.pop(key), student_setup.discard
    for node in nodes:
        if isinstance(node, ast.Call) and _is_session_pop_of_key(node) and node.args:
            lawful.add(id(node.args[0]))
        if (isinstance(node, ast.Attribute) and node.attr in SETUP_STORE_CLEANUP
                and isinstance(node.value, ast.Name) and node.value.id == SETUP_STORE):
            lawful.add(id(node.value))
    for node in nodes:
        if id(node) in lawful:
            continue
        if isinstance(node, ast.Constant) and node.value in ONBOARDING_KEYS:
            reasons.add(f"session key {node.value!r}")
        elif isinstance(node, ast.Name) and node.id in module.key_aliases:
            reasons.add(f"session key alias {node.id}")
        elif isinstance(node, ast.Name) and node.id in ESTABLISHMENT_COMMANDS:
            reasons.add(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in ESTABLISHMENT_COMMANDS:
            reasons.add(node.attr)
        elif isinstance(node, ast.Name) and node.id == SETUP_STORE:
            reasons.add('setup store')
        elif isinstance(node, ast.ImportFrom):
            names = {a.name for a in node.names}
            if (node.module or '').endswith('.' + SETUP_STORE) and not names <= SETUP_STORE_CLEANUP:
                reasons.add('setup store')
            reasons.update(names & ESTABLISHMENT_COMMANDS)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            calls.add(node.func.id)
    return reasons, calls


def establishment_touches(sources: dict[str, str]) -> dict[tuple[str, str], set[str]]:
    """Map (module, function) -> why it touches establishment state; untouched omitted.

    ``sources`` maps dotted module names to their source text. Pure over that text.
    """
    modules = {name: _index(text) for name, text in sources.items()}
    direct: dict[tuple[str, str], set[str]] = {}
    edges: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for module_name, module in modules.items():
        for function_name, nodes in module.functions.items():
            key = (module_name, function_name)
            direct[key], edges[key] = set(), set()
            for node in nodes:
                reasons, calls = _direct(node, module)
                direct[key] |= reasons
                for called in calls:
                    if called in module.functions:
                        edges[key].add((module_name, called))
                    elif called in module.imported and module.imported[called][0] in modules:
                        edges[key].add(module.imported[called])
    touched = {key: set(reasons) for key, reasons in direct.items()}
    changed = True
    while changed:
        changed = False
        for key, targets in edges.items():
            for target in targets:
                inherited = {f"via {target[1]}()"} if touched.get(target) else set()
                if inherited and not inherited <= touched[key]:
                    touched[key] |= inherited
                    changed = True
    return {key: reasons for key, reasons in touched.items() if reasons}


def undeclared_establishment_endpoints(
    sources: dict[str, str],
    views: dict[str, tuple[str, str]],
    declared: frozenset[str] | set[str],
) -> list[str]:
    """Endpoints whose view touches establishment state but is not declared.

    ``views`` maps endpoint -> (module, function name) of its view function.
    """
    touched = establishment_touches(sources)
    return sorted(
        f"{endpoint} ({', '.join(sorted(touched[view]))})"
        for endpoint, view in views.items()
        if view in touched and endpoint not in declared
    )
