from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient

from app.ai.structured import AssistantIntent
from app.api import chat
from app.api.dependencies import Principal, principal
from app.config import Settings
from app.main import create_app


async def test_assistant_uses_shared_quota_and_only_database_facts(database, workspace_factory, monkeypatch):
    owner = await workspace_factory()
    other = await workspace_factory()
    async with database.connection() as connection:
        await connection.execute(
            "insert into public.demo_sessions(token_hash,workspace_id,actor_id,manifest_sha256) values(%s,%s,%s,%s)",
            ("a" * 64, owner["workspace"], owner["user"], "b" * 64),
        )
    app = create_app(Settings(environment="test", demo_ai_call_limit=1))
    app.state.database = database
    app.dependency_overrides[principal] = lambda: Principal(owner["user"], owner["workspace"], "admin")
    provider = AsyncMock()
    provider.route_question.return_value = (AssistantIntent(intent="progress"), {})
    monkeypatch.setattr(chat, "create_provider", lambda settings: provider)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        answer = (await client.post("/api/v1/chat", json={"message": "What ought I do next?"})).json()
        assert answer["method"] == "ai_routed_summary"
        assert "1 emails" in answer["answer"]
        assert {x["caseId"] for x in answer["citations"]} == {str(owner["case"])}
        limited = (await client.post("/api/v1/chat", json={"message": "What ought I do next?"})).json()
        assert limited["fallback_reason"] == "DEMO_AI_LIMIT"
        assert provider.route_question.await_count == 1
        summary = (await client.post("/api/v1/chat", json={"message": "status"})).json()
        assert summary["method"] == "read_only_summary"
        assert "1 emails" in summary["answer"]
        assert str(other["case"]) not in str(summary)
