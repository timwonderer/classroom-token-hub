"""Helpers for signed opaque references used in route paths."""

from itsdangerous import BadSignature, URLSafeSerializer
from flask import current_app


OPAQUE_REF_SALT = "cth-opaque-ref-v1"


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(current_app.config["SECRET_KEY"], salt=OPAQUE_REF_SALT)


def make_opaque_ref(kind: str, record_id: int) -> str:
    """Create an opaque, signed reference for a record."""
    return _serializer().dumps({"k": kind, "i": int(record_id)})


def resolve_opaque_ref(kind: str, ref: str) -> int | None:
    """Resolve an opaque reference back to an integer id.

    Returns None when the token is invalid or does not match the expected kind.
    """
    try:
        payload = _serializer().loads(ref)
    except BadSignature:
        return None

    if not isinstance(payload, dict):
        return None
    if payload.get("k") != kind:
        return None

    record_id = payload.get("i")
    try:
        return int(record_id)
    except (TypeError, ValueError):
        return None
