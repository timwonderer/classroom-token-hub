"""Fail-closed validation of Google Cloud IAP identity assertions."""

from __future__ import annotations

import os

from google.auth import exceptions as google_auth_exceptions
from google.auth import jwt
from google.auth.transport import requests
from google.oauth2 import id_token


IAP_ISSUER = "https://cloud.google.com/iap"
IAP_CERTS_URL = "https://www.gstatic.com/iap/verify/public_key"
# IAP signs every assertion with ES256. The algorithm is pinned before
# verification because google-auth picks its verifier from the token header:
# a header naming RS256 hands IAP's EC key to the RSA verifier, which raises
# TypeError instead of rejecting.
IAP_ALGORITHM = "ES256"


def _allowlisted_email(value: str | None, allowlist: set[str]) -> str | None:
    email = str(value or "").strip().lower()
    return email if email in allowlist else None


def _verified_iap_claims(assertion: str, audience: str) -> dict | None:
    """Claims of an IAP assertion whose signature, expiry, audience and issuer verify.

    Only a failed verification means "not authenticated". Any other exception
    is a defect here and propagates, rather than reading as a rejected operator.
    """
    try:
        if jwt.decode_header(assertion).get("alg") != IAP_ALGORITHM:
            return None
        claims = id_token.verify_token(assertion, requests.Request(), audience=audience, certs_url=IAP_CERTS_URL)
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
