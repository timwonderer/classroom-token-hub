"""Auth username normalization and hashing utilities."""

from __future__ import annotations

from app.hash_utils import get_random_salt, hash_username, hash_username_lookup


def normalize_auth_username(username: str | None) -> str:
    return (username or "").strip()


def needs_hashed_username_migration(entity) -> bool:
    """True when an auth entity still lacks hashed username fields."""
    return not getattr(entity, "username_hash", None) or not getattr(entity, "username_lookup_hash", None)


def build_hashed_username_fields(username: str, *, existing_salt: bytes | None = None) -> tuple[bytes, str, str]:
    salt = existing_salt or get_random_salt()
    username_hash = hash_username(username, salt)
    username_lookup_hash = hash_username_lookup(username)
    return salt, username_hash, username_lookup_hash
