import json

import httpx
import pytest

from app.ai.morpheus import MorpheusClient
from app.config import Settings
from app.domain.errors import DomainError
from app.domain.models import StrictModel
from app.infrastructure.storage import Storage


class Output(StrictModel):
    result: int


@pytest.mark.parametrize(
    "status,content,finish,expected",
    [
        (200, '{"result":1}', "stop", None),
        (200, '{"result":1,"result":2}', "stop", "PROVIDER_OUTPUT_INVALID"),
        (200, '{"result":1}', "length", "PROVIDER_OUTPUT_INVALID"),
        (429, "", "stop", "PROVIDER_RATE_LIMITED"),
        (401, "", "stop", "PROVIDER_UNAVAILABLE"),
    ],
)
async def test_provider_contract_and_failures(status, content, finish, expected):
    requests = []

    def handle(request):
        requests.append(request)
        assert request.url.host == "api.mor.org"
        assert json.loads(request.content)["model"] == "deepseek-v4-pro"
        return httpx.Response(
            status, json={"choices": [{"finish_reason": finish, "message": {"content": content}}]}
        )

    client = MorpheusClient(
        Settings(morpheus_api_key="test-only", morpheus_model="deepseek-v4-pro"),
        httpx.AsyncClient(transport=httpx.MockTransport(handle)),
    )
    try:
        if expected:
            with pytest.raises(DomainError) as error:
                await client._generate("Synthetic input", Output.model_json_schema(), Output)
            assert error.value.code == expected
        else:
            result, metadata = await client._generate(
                "Synthetic input", Output.model_json_schema(), Output
            )
            assert result.result == 1
            assert metadata["provider"] == "morpheus"
        assert len(requests) == 1
    finally:
        await client.close()


def test_modern_supabase_keys_are_not_used_as_jwts():
    storage = Storage(
        Settings(
            supabase_url="https://example.supabase.co",
            supabase_service_role_key="sb_secret_test-only",
        )
    )
    assert storage.headers() == {"apikey": "sb_secret_test-only"}
