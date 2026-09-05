"""Fail-closed validation of Google Cloud IAP identity assertions."""

from __future__ import annotations

import os

from google.auth import jwt
from google.auth.transport import requests


IAP_ISSUER = "https://cloud.google.com/iap"
IAP_CERTS_URL = "https://www.gstatic.com/iap/verify/public_key"


def _allowlisted_email(value: str | None, allowlist: set[str]) -> str | None:
    email = str(value or "").strip().lower()
    return email if email in allowlist else None


def authenticated_operator_email(assertion: str | None, authenticated_email: str | None = None) -> str | None:
    audience = os.environ.get("IAP_AUDIENCE", "").strip()
    allowlist = {value.strip().lower() for value in os.environ.get("STATUS_OPERATOR_ALLOWLIST", "").split(",") if value.strip()}
    if not allowlist:
        return None

    if assertion and audience:
        try:
            claims = jwt.decode(assertion, certs_url=IAP_CERTS_URL, audience=audience, request=requests.Request())
        except Exception:
            claims = None
        if claims and claims.get("iss") == IAP_ISSUER:
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
