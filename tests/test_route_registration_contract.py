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
    # Second batch: superseded by live routes or unused, each with its tests
    # moved to the live path first (REF-API-001 §VII-D).
    "/admin/student/delete",
    "/admin/student/archive",
    "/admin/pending-students/delete",
    "/admin/pending-students/bulk-delete",
    "/admin/student/add-individual",
    "/admin/bonuses",
    "/admin/passkey/list",
    "/switch-view",
    "/sysadmin/auth-check",
]


@pytest.mark.parametrize("path", REMOVED_ROUTES)
def test_removed_dead_routes_stay_removed(app, path):
    registered = {str(rule) for rule in _rules(app)}
    assert path not in registered, (
        f"{path} was removed as a dead endpoint and must not be re-registered "
        "without a caller. See REF-API-001 §VII-D."
    )


# Endpoint names also live outside the URL map, in sets that grant or route
# behaviour by name. Removing a route leaves its name behind in them, silently:
# `admin.onboarding_skip` stayed in `_CLASSLESS_ADMIN_ENDPOINTS` after its route
# was deleted (2026-09-27). A stale name grants nothing today, but it is the
# spelling a future route of the same name would inherit an exemption through.
def _endpoint_name_registries():
    from app.auth import _CLASSLESS_ADMIN_ENDPOINTS
    from app.observability import CAPABILITY_BY_ENDPOINT
    from app.routes.admin import ADMIN_FEATURE_ENDPOINTS
    from app.routes.student import STUDENT_FEATURE_ENDPOINTS, _SURVIVING_PREMIUM_ENDPOINTS
    from app.services.tlcp import DEFAULT_NO_CONTEXT_ENDPOINTS, DEFAULT_PUBLIC_ENDPOINTS

    return {
        "auth._CLASSLESS_ADMIN_ENDPOINTS": set(_CLASSLESS_ADMIN_ENDPOINTS),
        "observability.CAPABILITY_BY_ENDPOINT": set(CAPABILITY_BY_ENDPOINT),
        "admin.ADMIN_FEATURE_ENDPOINTS": set(ADMIN_FEATURE_ENDPOINTS),
        "student.STUDENT_FEATURE_ENDPOINTS": set(STUDENT_FEATURE_ENDPOINTS),
        "student._SURVIVING_PREMIUM_ENDPOINTS": set(_SURVIVING_PREMIUM_ENDPOINTS),
        "tlcp.DEFAULT_PUBLIC_ENDPOINTS": set(DEFAULT_PUBLIC_ENDPOINTS),
        "tlcp.DEFAULT_NO_CONTEXT_ENDPOINTS": set(DEFAULT_NO_CONTEXT_ENDPOINTS),
    }


def unregistered_endpoint_names(registries, registered):
    """Return ``registry: [names]`` for every name no rule is registered under."""
    return {
        registry: sorted(names - registered)
        for registry, names in registries.items()
        if names - registered
    }


def test_every_endpoint_name_in_a_registry_is_registered(app):
    registered = {rule.endpoint for rule in _rules(app)}
    stale = unregistered_endpoint_names(_endpoint_name_registries(), registered)
    assert not stale, f"endpoint names with no registered route: {stale}"


def test_unregistered_endpoint_names_reports_a_removed_route():
    """Mutation proof (SOP-TEST-003 §IX.A): the exact stale name this guard
    was written after, beside a live sibling that must not be reported."""
    registries = {"auth._CLASSLESS_ADMIN_ENDPOINTS": {"admin.onboarding_skip", "admin.onboarding_skip_task"}}
    registered = {"admin.onboarding_skip_task"}
    assert unregistered_endpoint_names(registries, registered) == {
        "auth._CLASSLESS_ADMIN_ENDPOINTS": ["admin.onboarding_skip"],
    }
