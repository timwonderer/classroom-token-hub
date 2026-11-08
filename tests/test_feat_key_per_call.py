"""FEAT-CORE-000 §III.3: an idempotency key is accepted or generated.

``key_per_call`` is the declaration that lets a FEAT entry generate the key.
Without it a missing key still warns, because that is how a route that should
carry a caller key (a store purchase) gets noticed.
"""

import logging

from app.feats.base import get_idempotency_key, requires_feat_context


@requires_feat_context("FEAT-TEST-PER-CALL", key_per_call=True)
def _per_call(idempotency_key=None):
    return get_idempotency_key()


@requires_feat_context("FEAT-TEST-CALLER-KEY")
def _caller_keyed(idempotency_key=None):
    return get_idempotency_key()


def test_key_per_call_generates_a_distinct_key_each_invocation(app, caplog):
    with app.app_context(), caplog.at_level(logging.WARNING, logger="app.feats.base"):
        first, second = _per_call(), _per_call()

    assert first.startswith("feat-test-per-call:_per_call:")
    assert first != second
    assert "missing idempotency_key" not in caplog.text


def test_key_per_call_keeps_a_caller_key(app):
    with app.app_context():
        assert _per_call(idempotency_key="caller:1") == "caller:1"


def test_undeclared_feat_without_a_key_still_warns(app, caplog):
    with app.app_context(), caplog.at_level(logging.WARNING, logger="app.feats.base"):
        assert _caller_keyed() is None

    assert "FEAT-TEST-CALLER-KEY (Blast=LOW) missing idempotency_key" in caplog.text


def test_FEAT_CORE_000_III_1__unauthenticated_issue_resolve_enters_no_feat(client, caplog):
    """A FEAT resolves its actor before anything else (FEAT-CORE-000 §III.1), so
    authentication runs outside it: a signed-out request never opens one."""
    caplog.set_level(logging.INFO, logger="app.feats.base")
    response = client.post("/admin/issues/any-issue/resolve", data={})

    assert response.status_code in (302, 401, 403)
    assert not [r for r in caplog.records if "FEAT-ENTRY: feat=FEAT-SUP-001" in r.getMessage()]
