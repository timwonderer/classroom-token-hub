"""Seat-claim enumeration control (audit S6).

`FEAT-IDEN-001`'s failure-scenario table (section VII) deliberately returns
distinguishable responses for invalid credentials vs. an already-claimed
seat -- useful claim-flow UX, but also an enumeration oracle, since
`/student/claim-account` previously had no rate limit at all (the route's
own comment said so: "rate-limited by nothing else on this route"). Operator
ruling (Tim, 2026-10-12): the distinguishing responses are fine; the gap is
that nothing budgeted attempts. This file is the regression guard for the
limiter, not for the responses, which stay as FEAT-IDEN-001 specifies.
"""

from __future__ import annotations

from app.extensions import limiter


def _post_claim(client, **overrides):
    data = {
        "join_code": "AAAA-BBBB",
        "first_name": "Nobody",
        "last_name": "Here",
        "dedupe_code": "",
    }
    data.update(overrides)
    return client.post("/student/claim-account", data=data)


def test_claim_account_is_rate_limited_per_ip(client, app):
    """A burst of claim attempts against an endpoint with no account to lock
    onto must still be bounded -- by IP, since there is no account yet.
    """
    app.config["RATELIMIT_ENABLED"] = True
    try:
        for _ in range(10):
            response = _post_claim(client)
            assert response.status_code != 429
        response = _post_claim(client)
        assert response.status_code == 429
    finally:
        app.config["RATELIMIT_ENABLED"] = False
        limiter.reset()


def test_claim_account_get_is_not_rate_limited(client, app):
    """Only the POST (the actual guess) is budgeted; loading the form is not."""
    app.config["RATELIMIT_ENABLED"] = True
    try:
        for _ in range(11):
            response = client.get("/student/claim-account")
            assert response.status_code == 200
    finally:
        app.config["RATELIMIT_ENABLED"] = False
        limiter.reset()
