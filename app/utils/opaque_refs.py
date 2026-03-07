"""Helpers for encrypted opaque references used in route paths."""

import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app
from itsdangerous import BadSignature, URLSafeSerializer


OPAQUE_REF_SALT = "cth-opaque-ref-v1"


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(current_app.config["SECRET_KEY"], salt=OPAQUE_REF_SALT)


def _fernet() -> Fernet:
    """Build a deterministic Fernet key from SECRET_KEY and salt."""
    secret = str(current_app.config["SECRET_KEY"])
    seed = f"{secret}:{OPAQUE_REF_SALT}".encode("utf-8")
    derived = hashlib.sha256(seed).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def _validate_payload(kind: str, payload: object) -> int | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("k") != kind:
        return None

    record_id = payload.get("i")
    try:
        return int(record_id)
    except (TypeError, ValueError):
        return None


def make_opaque_ref(kind: str, record_id: int) -> str:
    """Create an opaque, encrypted reference for a record."""
    payload = {"k": kind, "i": int(record_id)}
    token = _fernet().encrypt(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return token.decode("utf-8")


def resolve_opaque_ref(kind: str, ref: str) -> int | None:
    """Resolve an opaque reference back to an integer id.

    Returns None when the token is invalid or does not match the expected kind.
    Accepts legacy signed-only tokens for backward compatibility.
    """
    try:
        decrypted = _fernet().decrypt(ref.encode("utf-8"))
        payload = json.loads(decrypted.decode("utf-8"))
        resolved = _validate_payload(kind, payload)
        if resolved is not None:
            return resolved
    except (InvalidToken, ValueError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        pass

    # Legacy signed-only token fallback.
    try:
        payload = _serializer().loads(ref)
    except BadSignature:
        return None
    return _validate_payload(kind, payload)
