"""Encrypt OAuth tokens before they are stored, so a database read alone never yields a usable token.

Stored values look like `fernet:v1:<token>`. An empty string stays empty (no token). A value without
the prefix is plaintext written before encryption existed; it is still readable so that it can be
revoked, but nothing new is ever written that way.
"""

from cryptography.fernet import Fernet, InvalidToken

from app.config import Settings
from app.domain.errors import DomainError

PREFIX = "fernet:v1:"


def _cipher(settings: Settings) -> Fernet:
    key = settings.token_encryption_key
    if key is None or not key.get_secret_value():
        raise DomainError(
            "TOKEN_KEY_MISSING", "TOKEN_ENCRYPTION_KEY is not configured on this server", status=503
        )
    try:
        return Fernet(key.get_secret_value().encode("ascii"))
    except ValueError as invalid:
        raise DomainError(
            "TOKEN_KEY_INVALID", "TOKEN_ENCRYPTION_KEY is not a valid Fernet key", status=503
        ) from invalid


def encryption_configured(settings: Settings) -> bool:
    try:
        _cipher(settings)
    except DomainError:
        return False
    return True


def seal(settings: Settings, token: str) -> str:
    if not token:
        return ""
    return PREFIX + _cipher(settings).encrypt(token.encode("utf-8")).decode("ascii")


def unseal(settings: Settings, stored: str) -> str:
    if not stored:
        return ""
    if not stored.startswith(PREFIX):
        return stored  # legacy plaintext, readable only so it can be revoked and cleared
    try:
        return _cipher(settings).decrypt(stored[len(PREFIX) :].encode("ascii")).decode("utf-8")
    except InvalidToken as wrong_key:
        raise DomainError(
            "TOKEN_UNREADABLE", "A stored token was encrypted with a different key", status=500
        ) from wrong_key
