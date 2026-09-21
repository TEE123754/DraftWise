"""Gmail OAuth tokens are encrypted at rest and revoked with Google on disconnect."""

import httpx
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from app.api import gmail
from app.config import Settings
from app.domain.errors import DomainError
from app.infrastructure.token_crypto import encryption_configured, seal, unseal


def settings(key=None):
    return Settings(environment="test", token_encryption_key=SecretStr(key) if key else None)


def test_a_sealed_token_is_not_the_token_and_opens_with_the_same_key():
    config = settings(Fernet.generate_key().decode())
    stored = seal(config, "ya29.secret-access-token")
    assert stored.startswith("fernet:v1:") and "ya29" not in stored
    assert unseal(config, stored) == "ya29.secret-access-token"


def test_a_different_key_cannot_open_it():
    stored = seal(settings(Fernet.generate_key().decode()), "1//refresh")
    with pytest.raises(DomainError) as raised:
        unseal(settings(Fernet.generate_key().decode()), stored)
    assert raised.value.code == "TOKEN_UNREADABLE"


def test_without_a_key_nothing_can_be_sealed_and_gmail_is_not_offered():
    with pytest.raises(DomainError) as raised:
        seal(settings(), "token")
    assert raised.value.code == "TOKEN_KEY_MISSING"
    assert encryption_configured(settings("not-a-fernet-key")) is False
    both = Settings(environment="test", google_client_id="id", google_client_secret=SecretStr("s"))
    assert gmail._configured(both) is False  # the OAuth client alone is not enough


def test_empty_and_legacy_plaintext_values_stay_readable_for_revocation():
    config = settings(Fernet.generate_key().decode())
    assert seal(config, "") == "" and unseal(config, "") == ""
    assert unseal(config, "legacy-plain-token") == "legacy-plain-token"


class Revoke:
    response: httpx.Response | Exception = httpx.Response(200)
    sent = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def post(self, url, data):
        Revoke.sent.append((url, data))
        if isinstance(Revoke.response, Exception):
            raise Revoke.response
        return Revoke.response


@pytest.fixture
def google(monkeypatch):
    monkeypatch.setattr(gmail.httpx, "AsyncClient", Revoke)
    Revoke.sent = []
    return Revoke


async def test_revocation_posts_the_token_to_google(google):
    google.response = httpx.Response(200)
    assert await gmail.revoke_token("1//refresh") is True
    assert google.sent == [(gmail.OAUTH_REVOKE_URL, {"token": "1//refresh"})]


async def test_an_already_revoked_token_counts_as_revoked(google):
    google.response = httpx.Response(400, json={"error": "invalid_token", "error_description": "Token expired or revoked"})
    assert await gmail.revoke_token("1//old") is True


@pytest.mark.parametrize("response", [httpx.Response(503), httpx.ConnectError("offline")])
async def test_an_outage_is_reported_as_not_revoked(google, response):
    google.response = response
    assert await gmail.revoke_token("1//refresh") is False
