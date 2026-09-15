"""Fail-closed validation of Google Cloud IAP identity assertions."""

from __future__ import annotations

import http.client
import json
import os
import re
import threading
import time

from google.auth import exceptions as google_auth_exceptions
from google.auth import jwt
from google.auth.transport import requests


IAP_ISSUER = "https://cloud.google.com/iap"
IAP_CERTS_URL = "https://www.gstatic.com/iap/verify/public_key"
# IAP signs every assertion with ES256. The algorithm is pinned before
# verification because google-auth picks its verifier from the token header:
# a header naming RS256 hands IAP's EC key to the RSA verifier, which raises
# TypeError instead of rejecting.
IAP_ALGORITHM = "ES256"
# Key fetches hold the cache lock, so a hung endpoint must not stall every
# operator request for google-auth's 120-second default.
KEY_FETCH_TIMEOUT_SECONDS = 10

_MAX_AGE = re.compile(r"(?:^|[\s,])max-age\s*=\s*\"?(\d+)", re.IGNORECASE)


def _allowlisted_email(value: str | None, allowlist: set[str]) -> str | None:
    email = str(value or "").strip().lower()
    return email if email in allowlist else None


def _fresh_for_seconds(headers) -> int:
    """How long a key-set response stays fresh, per its Cache-Control and Age headers."""
    values = {str(name).lower(): str(value) for name, value in dict(headers or {}).items()}
    cache_control = values.get("cache-control", "")
    directives = {part.split("=", 1)[0].strip().lower() for part in cache_control.split(",")}
    max_age = _MAX_AGE.search(cache_control)
    if max_age is None or directives & {"no-store", "no-cache"}:
        return 0
    age = values.get("age", "").strip()
    return max(int(max_age.group(1)) - (int(age) if age.isdigit() else 0), 0)


class _IapKeyCache:
    """IAP's public key set, held for as long as the key endpoint says it is fresh.

    One entry, replaced whole by every fetch. An assertion naming a key the
    entry lacks forces a fetch before it is rejected, so a key IAP has just
    rotated in is used at once rather than after the entry expires. At worst a
    run of unknown key ids fetches once per request, which is what every
    verification cost before there was a cache. A failed fetch leaves the entry
    as it was.
    """

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._keys: dict[str, str] = {}
        self._fresh_until = float("-inf")

    def keys_for(self, key_id: str | None, request) -> dict[str, str]:
        with self._lock:
            if self._clock() >= self._fresh_until or (key_id is not None and key_id not in self._keys):
                self._fetch(request)
            return self._keys

    def _fetch(self, request) -> None:
        response = request(url=IAP_CERTS_URL, method="GET", timeout=KEY_FETCH_TIMEOUT_SECONDS)
        if response.status != http.client.OK:
            raise google_auth_exceptions.TransportError(f"Could not fetch IAP keys: HTTP {response.status}")
        keys = json.loads(response.data.decode("utf-8"))
        if not isinstance(keys, dict):
            raise ValueError("IAP key set is not a JSON object")
        self._keys = keys
        self._fresh_until = self._clock() + _fresh_for_seconds(response.headers)


_IAP_KEYS = _IapKeyCache()


def _verified_iap_claims(assertion: str, audience: str) -> dict | None:
    """Claims of an IAP assertion whose signature, expiry, audience and issuer verify.

    Only a failed verification means "not authenticated". Any other exception
    is a defect here and propagates, rather than reading as a rejected operator.
    """
    try:
        header = jwt.decode_header(assertion)
        key_id = header.get("kid")
        # google-auth looks the kid up in the key set, where an unhashable one
        # (a list or object) raises TypeError instead of rejecting.
        if header.get("alg") != IAP_ALGORITHM or not isinstance(key_id, (str, type(None))):
            return None
        keys = _IAP_KEYS.keys_for(key_id, requests.Request())
        claims = jwt.decode(assertion, certs=keys, audience=audience)
    except (ValueError, google_auth_exceptions.GoogleAuthError):
        return None
    return claims if claims.get("iss") == IAP_ISSUER else None


def authenticated_operator_email(assertion: str | None, authenticated_email: str | None = None) -> str | None:
    audience = os.environ.get("IAP_AUDIENCE", "").strip()
    allowlist = {value.strip().lower() for value in os.environ.get("STATUS_OPERATOR_ALLOWLIST", "").split(",") if value.strip()}
    if not allowlist:
        return None

    if assertion and audience:
        claims = _verified_iap_claims(assertion, audience)
        if claims:
            operator = _allowlisted_email(claims.get("email"), allowlist)
            if operator:
                return operator

    # Cloud Run's direct IAP integration supplies the authenticated email header
    # after enforcing IAP at the service boundary. The operator service is
    # deployed with internal-and-cloud-load-balancing ingress, so direct public
    # requests cannot supply this trusted header to the container.
    if os.environ.get("IAP_TRUSTED_EMAIL_HEADER", "").strip().lower() == "true":
        value = authenticated_email or ""
        if value.startswith("accounts.google.com:"):
            value = value.split(":", 1)[1]
        return _allowlisted_email(value, allowlist)
    return None
