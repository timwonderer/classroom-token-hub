"""
Custom encryption types for securing PII (Personally Identifiable Information).

This module provides SQLAlchemy custom type decorators and helper functions for
encrypting sensitive data at rest using Fernet (AES encryption).
"""

import os
import base64
from sqlalchemy.types import TypeDecorator, LargeBinary
from cryptography.fernet import Fernet, InvalidToken


class PIIEncryptedType(TypeDecorator):
    """Custom AES encryption for PII fields using Fernet."""
    impl = LargeBinary
    cache_ok = True

    def __init__(self, key_env_var, *args, **kwargs):
        key = os.getenv(key_env_var)
        if not key:
            raise RuntimeError(f"Missing required environment variable: {key_env_var}")
        self.fernet = Fernet(key)
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            value = value.encode('utf-8')
        return self.fernet.encrypt(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        decrypted = self.fernet.decrypt(value)
        return decrypted.decode('utf-8')


# Helper functions for encrypting TOTP secrets (and other sensitive strings)
def _get_fernet():
    """Get Fernet cipher instance using ENCRYPTION_KEY environment variable."""
    key = os.getenv('ENCRYPTION_KEY')
    if not key:
        raise RuntimeError("Missing required environment variable: ENCRYPTION_KEY")
    return Fernet(key)


def encrypt_totp(plaintext_secret):
    """
    Encrypt a TOTP secret and return base64-encoded string suitable for database storage.

    Args:
        plaintext_secret (str): The plaintext TOTP secret (e.g., "JBSWY3DPEHPK3PXP")

    Returns:
        str: Base64-encoded encrypted secret
    """
    if not plaintext_secret:
        return None

    fernet = _get_fernet()
    encrypted_bytes = fernet.encrypt(plaintext_secret.encode('utf-8'))
    # Return as base64 string for storage in VARCHAR column
    return base64.b64encode(encrypted_bytes).decode('utf-8')


def is_totp_encrypted(value):
    """Return True if the value appears to be a valid encrypted TOTP payload."""
    if not value:
        return False
    try:
        fernet = _get_fernet()
        encrypted_bytes = base64.b64decode(value.encode('utf-8'))
        fernet.decrypt(encrypted_bytes)
        return True
    except (InvalidToken, ValueError, TypeError, base64.binascii.Error):
        return False


def normalize_totp_for_storage(secret_value):
    """
    Ensure a TOTP secret is stored encrypted.

    If value is already encrypted with current key, keep it unchanged.
    Otherwise, encrypt it as plaintext input.
    """
    if not secret_value:
        return None
    if is_totp_encrypted(secret_value):
        return secret_value
    return encrypt_totp(secret_value)


def decrypt_totp(encrypted_secret):
    """
    Decrypt a TOTP secret from base64-encoded encrypted string.

    Args:
        encrypted_secret (str): Base64-encoded encrypted secret

    Returns:
        str: Plaintext TOTP secret
    """
    if not encrypted_secret:
        return None

    try:
        fernet = _get_fernet()
        encrypted_bytes = base64.b64decode(encrypted_secret.encode('utf-8'))
        decrypted = fernet.decrypt(encrypted_bytes)
        return decrypted.decode('utf-8')
    except (InvalidToken, ValueError, TypeError, base64.binascii.Error):
        raise ValueError("Invalid encrypted TOTP secret format")
