"""Request-derived values can't forge log lines (CodeQL py/log-injection,
GitHub alerts #294 and #296–#302).

The error handlers in ``wsgi.py`` and the Cloudflare-mismatch warning in
``app/__init__.py`` interpolate ``request.url``/``request.path`` straight
into a log line. Checked directly (see the tests below): Werkzeug's
``request.url`` keeps percent-encoding, so a ``%0D%0A`` sent in the request
line reaches it as literal text, not a decoded CR/LF -- the 7 ``request.url``
sites in wsgi.py are less exposed than CodeQL's generic "depends on a
user-provided value" alert implies, though they're still wrapped in
``sanitize_for_log()`` as defense in depth. ``request.path``, by contrast,
*does* decode it to a real CR/LF, which is where the actual risk sits.

A wider, CodeQL-missed instance of exactly that was found while fixing this:
``RequestIdFilter`` in ``app/__init__.py`` falls back to the raw
``request.path`` for every log record's ``endpoint`` field whenever
``request.url_rule`` is unset (every unmatched route, i.e. every 404) -- not
just the handful of explicit ``logger.warning(f"...")`` call sites CodeQL's
taint analysis follows into a sink. That one line carries a real, decoded
CRLF into the ``endpoint=`` field of *every* log statement during that
request, which is a materially bigger attack surface than the 8 flagged
alerts alone.
"""

from __future__ import annotations

from unittest.mock import patch

import wsgi  # noqa: F401 -- registers the error handlers this fix touches

from app.utils.helpers import sanitize_for_log


# --------------------------------------------------------------------------
# Unit tests — the sanitizer itself
# --------------------------------------------------------------------------

def test_sanitizer_escapes_cr_and_lf():
    assert sanitize_for_log("a\r\nFAKE LOG LINE") == "a\\x0d\\x0aFAKE LOG LINE"


def test_sanitizer_escapes_other_control_characters():
    assert sanitize_for_log("tab\tbell\x07esc\x1b[31m") == "tab\\x09bell\\x07esc\\x1b[31m"


def test_sanitizer_is_quiet_on_ordinary_text():
    assert sanitize_for_log("/student/dashboard?x=1") == "/student/dashboard?x=1"


def test_sanitizer_coerces_non_strings():
    assert sanitize_for_log(None) == "None"
    assert sanitize_for_log(404) == "404"


# --------------------------------------------------------------------------
# Behavioural regression — the real log line can no longer be split
# --------------------------------------------------------------------------

def _messages(mock_logger_method, needle):
    """Fully-formatted messages (as logging would emit them: ``%s`` already
    substituted) from calls whose first arg contains ``needle``."""
    out = []
    for call in mock_logger_method.call_args_list:
        args = call.args
        if not args or needle not in str(args[0]):
            continue
        out.append(args[0] % args[1:] if len(args) > 1 else args[0])
    return out


def test_404_handler_logs_request_url_unchanged_when_it_carries_no_raw_control_chars(app):
    """request.url keeps percent-encoding (confirmed: a %0D%0A in the request
    line reaches it as the literal text ``%0D%0A``, never a decoded CR/LF),
    so sanitize_for_log is a no-op here today -- this site's real exposure is
    smaller than CodeQL's alert implies. The call is still wrapped (see the
    RequestIdFilter test below and test_sanitizer_escapes_cr_and_lf for the
    sites that do carry a decoded, attacker-controlled value) as defense in
    depth against a future change to what reaches this log line."""
    client = app.test_client()
    with patch.object(app.logger, "warning") as mock_warning:
        response = client.get("/does-not-exist%0d%0aFAKE-INJECTED-LINE/x")

    assert response.status_code == 404

    lines = _messages(mock_warning, "404 Not Found")
    assert len(lines) == 1
    assert "\r" not in lines[0] and "\n" not in lines[0]
    assert "%0D%0AFAKE-INJECTED-LINE" in lines[0]


def test_sanitizer_would_neutralize_a_raw_control_character_reaching_this_site():
    """If request.url ever did carry a decoded control character (a future
    Werkzeug change, a different WSGI server), sanitize_for_log -- which the
    404/403/401/400/429/503 handlers and the Cloudflare-mismatch warning all
    now call on it -- still prevents the line split, proven directly against
    the detector the previous test can't actually trigger today."""
    malicious_url = "http://localhost/x\r\nFAKE-INJECTED-LINE"
    assert sanitize_for_log(malicious_url) == "http://localhost/x\\x0d\\x0aFAKE-INJECTED-LINE"


def _record_with_request_id_filter(app):
    """A bare LogRecord run through RequestIdFilter, inside the active
    request context, the way the real logging.Filter machinery does it."""
    import logging

    from app import RequestIdFilter

    record = logging.LogRecord("app", logging.WARNING, __file__, 1, "test", (), None)
    RequestIdFilter().filter(record)
    return record


def test_request_id_filter_endpoint_fallback_is_sanitized(app):
    """The RequestIdFilter fallback this fix added -- not one of the explicit
    logger.warning() call sites, but reached by every log record on every
    unmatched route (request.url_rule is None), not just a 404 handler's own
    warning call."""
    with app.test_request_context("/does-not-exist%0d%0aFAKE-INJECTED-LINE/x"):
        record = _record_with_request_id_filter(app)

    assert "\r" not in record.endpoint and "\n" not in record.endpoint
    assert "\\x0d\\x0a" in record.endpoint
    assert "FAKE-INJECTED-LINE" in record.endpoint


def test_matched_route_endpoint_is_the_route_rule_not_the_path(app):
    """Quiet on the ordinary case: a matched route still logs its rule, not
    request.path, so this fix must not have broken that."""
    with app.test_request_context("/student/login"):
        from flask import request

        assert request.url_rule is not None, "fixture route must resolve to a rule"
        expected_rule = request.url_rule.rule
        record = _record_with_request_id_filter(app)

    assert record.endpoint == expected_rule
    assert "\\x" not in record.endpoint
