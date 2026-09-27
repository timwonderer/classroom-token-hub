"""Every registered rule must be able to call its view function.

A route decorator whose function body is deleted does not raise at import time.
It silently binds to the *next* function in the file, and the resulting rule
advertises a capability that 500s on every request. `/admin/payroll/rewards/add`
shipped in exactly that state: the rule supplied no `transaction_id` but bound
to `void_payroll_transaction(transaction_id)`.

Nothing else in the suite would notice, because the broken route has no caller
to fail.
"""

import inspect

import pytest


def _view_signature(app, endpoint):
    return inspect.signature(inspect.unwrap(app.view_functions[endpoint]))


def _rules(app):
    return [r for r in app.url_map.iter_rules() if r.endpoint != "static"]


def test_every_rule_supplies_the_arguments_its_view_requires(app):
    broken = []
    for rule in _rules(app):
        try:
            signature = _view_signature(app, rule.endpoint)
        except (TypeError, ValueError):  # C-implemented or wrapped beyond reach
            continue
        required = {
            name
            for name, param in signature.parameters.items()
            if param.default is inspect.Parameter.empty
            and param.kind
            in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        }
        missing = required - set(rule.arguments)
        if missing:
            broken.append(f"{rule} -> {rule.endpoint} missing {sorted(missing)}")
    assert not broken, "rules that cannot call their view:\n" + "\n".join(broken)


def test_no_rule_passes_arguments_its_view_cannot_accept(app):
    broken = []
    for rule in _rules(app):
        try:
            signature = _view_signature(app, rule.endpoint)
        except (TypeError, ValueError):
            continue
        accepts_kwargs = any(
            p.kind is inspect.Parameter.VAR_KEYWORD
            for p in signature.parameters.values()
        )
        if accepts_kwargs:
            continue
        extra = set(rule.arguments) - set(signature.parameters)
        if extra:
            broken.append(f"{rule} -> {rule.endpoint} cannot accept {sorted(extra)}")
    assert not broken, "rules passing unaccepted arguments:\n" + "\n".join(broken)


# These execute without a session and reach application state. `/debug/filters`
# returns the Jinja filter list (framework fingerprinting); `/debug/admin-db-test`
# queries the users table and reports a teacher count. Neither has a caller.
PROHIBITED_ROUTES = ["/debug/filters", "/debug/admin-db-test"]


@pytest.mark.parametrize("path", PROHIBITED_ROUTES)
def test_debug_routes_are_not_registered(app, path):
    registered = {str(rule) for rule in _rules(app)}
    assert path not in registered, (
        f"{path} is an unauthenticated debug endpoint and must not be registered. "
        "See REF-API-001 §VIII-A."
    )


# Removed 2026-09-27 as dead endpoints (REF-API-001 §VII-D). The first is the
# reason this list exists: with only a teacher's hall-pass verification token it
# returned the day's passes across that teacher's classes -- names, internal
# seat and class ids -- without the class and full-name inputs the verification
# page requires (INV-ARC-019 §X). The rest had no caller. A route with no caller
# is invisible to every other test, so re-adding one would pass silently.
REMOVED_ROUTES = [
    "/api/hall-pass/verification/active",
    "/admin/api/economy/calculate-cwi",
    "/admin/onboarding/skip",
    "/sysadmin/passkey/list",
    "/admin/payroll/transactions/<int:transaction_id>/void",
    "/admin/payroll/transactions/void-bulk",
    "/admin/export-class-roster",
    "/student/switch-period/<int:user_id>",
    "/student/dismiss-recovery/<int:code_id>",
]


@pytest.mark.parametrize("path", REMOVED_ROUTES)
def test_removed_dead_routes_stay_removed(app, path):
    registered = {str(rule) for rule in _rules(app)}
    assert path not in registered, (
        f"{path} was removed as a dead endpoint and must not be re-registered "
        "without a caller. See REF-API-001 §VII-D."
    )
