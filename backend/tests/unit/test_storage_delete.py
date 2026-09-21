from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.domain.errors import DomainError
from app.infrastructure import storage as storage_module
from app.infrastructure.storage import Storage


def settings(key="sb_secret_x", url="https://project.supabase.test"):
    return SimpleNamespace(
        supabase_service_role_key=SecretStr(key) if key else None, supabase_url=url, storage_bucket="originals",
    )


class FakeClient:
    status = 200
    seen = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def delete(self, url, headers):
        FakeClient.seen.append((url, headers))
        return SimpleNamespace(status_code=FakeClient.status, is_success=200 <= FakeClient.status < 300)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(storage_module.httpx, "AsyncClient", FakeClient)
    FakeClient.seen = []
    return FakeClient


async def test_delete_calls_the_private_bucket_with_the_service_key(client):
    await Storage(settings()).delete("uploads/ws/id/my file.pdf")
    url, headers = client.seen[0]
    assert url == "https://project.supabase.test/storage/v1/object/originals/uploads/ws/id/my%20file.pdf"
    assert headers == {"apikey": "sb_secret_x"}


async def test_an_object_that_is_already_gone_counts_as_deleted_so_retries_are_safe(client):
    client.status = 404
    await Storage(settings()).delete("uploads/ws/id/gone.pdf")


async def test_a_storage_error_is_reported_as_retryable(client):
    client.status = 503
    with pytest.raises(DomainError) as raised:
        await Storage(settings()).delete("uploads/ws/id/a.pdf")
    assert raised.value.retryable and raised.value.code == "STORAGE_UNAVAILABLE"


@pytest.mark.parametrize("key", ["demo-seed/ws/id/attachments/a.txt", "linked-source/ws/id/uploads/ws/x/a.pdf"])
async def test_a_bundled_demo_file_or_a_link_is_never_deleted(client, key):
    with pytest.raises(DomainError) as raised:
        await Storage(settings()).delete(key)
    assert raised.value.code == "STORAGE_KEY_NOT_PHYSICAL" and client.seen == []


def test_configured_needs_both_the_key_and_the_url():
    assert Storage(settings()).configured() is True
    assert Storage(settings(key=None)).configured() is False
    assert Storage(settings(url="")).configured() is False
