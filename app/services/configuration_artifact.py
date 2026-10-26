"""Strict, authenticated transfer documents (SPEC-CLASS-001); no database access."""
import hashlib
import json
import math
from datetime import datetime

from flask import current_app
from itsdangerous import BadData, Serializer

MAX_BYTES = 1024 * 1024
MAX_ENTRIES = 1000


class ConfigurationError(ValueError):
    pass


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ConfigurationError("Duplicate JSON field")
        result[key] = value
    return result


def _constant(value):
    raise ConfigurationError("Nonfinite numbers are not permitted")


def _depth(value, depth=0):
    if depth > 20:
        raise ConfigurationError("Configuration is nested too deeply")
    if isinstance(value, float) and not math.isfinite(value):
        raise ConfigurationError("Nonfinite numbers are not permitted")
    if isinstance(value, dict):
        for child in value.values():
            _depth(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _depth(child, depth + 1)


class StrictJSON:
    @staticmethod
    def dumps(value):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)

    @staticmethod
    def loads(value):
        try:
            result = json.loads(value, object_pairs_hook=_pairs, parse_constant=_constant)
            _depth(result)
            return result
        except (ValueError, TypeError, RecursionError) as exc:
            raise ConfigurationError("Invalid configuration JSON") from exc


def _serializer(purpose):
    key = current_app.config.get("CONFIGURATION_EXPORT_KEY")
    if not isinstance(key, str) or not key.strip():
        raise ConfigurationError("Configuration transfer is not configured")
    return Serializer(key, salt="cth-configuration-" + purpose + "-v1", serializer=StrictJSON,
                      signer_kwargs={"digest_method": hashlib.sha256, "key_derivation": "hmac"})


def sign(value, purpose):
    _depth(value)
    result = _serializer(purpose).dumps(value)
    result = result.encode("utf-8") if isinstance(result, str) else result
    if len(result) > MAX_BYTES:
        raise ConfigurationError("Configuration exceeds the 1 MiB limit")
    return result


def verify(raw, purpose):
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ConfigurationError("Configuration exceeds the 1 MiB limit")
    try:
        return _serializer(purpose).loads(raw)
    except (BadData, UnicodeError, ValueError, RecursionError) as exc:
        raise ConfigurationError("Configuration is invalid or its signature cannot be verified") from exc


def digest(raw):
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def instant(value):
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None:
            raise ValueError
        return result
    except (TypeError, ValueError):
        raise ConfigurationError("An explicit date, time and timezone is required")
