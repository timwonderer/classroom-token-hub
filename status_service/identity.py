"""Fail-closed validation of Google Cloud IAP identity assertions."""

from __future__ import annotations

import os

from google.auth import jwt
from google.auth.transport import requests


IAP_ISSUER = "https://cloud.google.com/iap"
IAP_CERTS_URL = "https://www.gstatic.com/iap/verify/public_key"


def authenticated_operator_email(assertion: str | None) -> str | None:
    if not assertion:
        return None
    audience = os.environ.get("IAP_AUDIENCE", "").strip()
    allowlist = {value.strip().lower() for value in os.environ.get("STATUS_OPERATOR_ALLOWLIST", "").split(",") if value.strip()}
    if not audience or not allowlist:
        return None
    try:
        claims = jwt.decode(assertion, certs_url=IAP_CERTS_URL, audience=audience, request=requests.Request())
    except Exception:
        return None
    if claims.get("iss") != IAP_ISSUER:
        return None
    email = str(claims.get("email", "")).strip().lower()
    return email if email in allowlist else None
