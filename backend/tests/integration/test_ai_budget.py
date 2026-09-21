import asyncio
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import ai_quality
from app.api.dependencies import Principal, principal
from app.config import Settings
from app.domain.errors import DomainError
from app.main import create_app
from app.services.bounded_ai import BoundedAI, usage
from app.services.classification import Classification


class Stub:
    """A provider that answers every classification as GENERAL and counts how often it was asked."""

    def __init__(self):
        self.calls = 0

    async def classify(self, subject, body, attachments):
        self.calls += 1
        answer = Classification(
            category="GENERAL", ambiguous=False, evidence_span_ids=("current",), reason_code="informational"
        )
        return answer, {"provider": "stub", "latency_ms": 1500}

    async def close(self):
        return None


async def test_the_daily_budget_caps_live_calls_and_an_identical_input_is_never_asked_twice(database, workspace_factory):
    context = await workspace_factory()
    settings = Settings(environment="test", ai_daily_budget=2)
    stub = Stub()
    ai = BoundedAI(stub, database, context["workspace"], settings)

    first, meta = await ai.classify("Invoice query", "Why was I charged twice?", [])
    again, meta_again = await ai.classify("Invoice query", "Why was I charged twice?", [])
    assert stub.calls == 1  # the second identical question came from the cache
    assert again == first and meta_again["cache"] == "hit" and "cache" not in meta

    await ai.classify("Different subject", "Different body", [])
    assert stub.calls == 2
    with pytest.raises(DomainError) as raised:
        await ai.classify("A third question", "Nothing left to spend", [])
    assert raised.value.code == "AI_BUDGET_REACHED" and stub.calls == 2  # refused before the provider was asked

    # The cache still answers when the budget is gone, at no cost.
    _, hit = await ai.classify("Different subject", "Different body", [])
    assert hit["cache"] == "hit"
    async with database.connection() as connection:
        assert await usage(connection, context["workspace"], settings) == {"scope": "day", "used": 2, "budget": 2}


async def test_a_zero_budget_means_no_live_ai_at_all(database, workspace_factory):
    context = await workspace_factory()
    stub = Stub()
    ai = BoundedAI(stub, database, context["workspace"], Settings(environment="test", ai_daily_budget=0))
    with pytest.raises(DomainError) as raised:
        await ai.classify("Hello", "Hello", [])
    assert raised.value.code == "AI_BUDGET_REACHED" and stub.calls == 0


async def test_one_workspace_cannot_spend_or_read_another_workspaces_budget_or_answers(database, workspace_factory):
    mine, other = await workspace_factory(), await workspace_factory()
    settings = Settings(environment="test", ai_daily_budget=1)
    await BoundedAI(Stub(), database, mine["workspace"], settings).classify("Same text", "Same text", [])
    theirs = Stub()
    await BoundedAI(theirs, database, other["workspace"], settings).classify("Same text", "Same text", [])
    assert theirs.calls == 1  # not a cache hit: answers are private to the workspace that paid for them
    async with database.connection() as connection:
        assert (await usage(connection, other["workspace"], settings))["used"] == 1


def tiny_set(count=2):
    """A labelled sample with no cached AI answers, so an evaluation must ask."""
    emails = {
        f"email_t{i}": SimpleNamespace(subject=f"Subject {i}", body=f"Body {i}, nothing decisive", attachments=())
        for i in range(count)
    }
    return {key: "GENERAL" for key in emails}, emails, {}


def client_for(app, context, role="admin"):
    app.dependency_overrides[principal] = lambda: Principal(context["user"], context["workspace"], role)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_a_live_evaluation_needs_the_exact_call_count_budget_and_a_provider(database, workspace_factory, monkeypatch):
    context = await workspace_factory()
    monkeypatch.setattr(ai_quality, "load_heldout", lambda root: tiny_set(2))
    app = create_app(Settings(environment="test", ai_daily_budget=1))
    app.state.database = database
    async with client_for(app, context) as client:
        plan = (await client.get("/api/v1/quality/ai-classifier")).json()
        assert plan["plan"]["to_call"] == 2
        assert plan["usage"] == {"scope": "day", "used": 0, "budget": 1, "remaining": 1}

        unconfirmed = await client.post("/api/v1/quality/ai-classifier/evaluate", json={"mode": "live"})
        assert unconfirmed.status_code == 409 and unconfirmed.json()["error"]["code"] == "CONFIRM_CALLS"
        assert "2 AI calls" in unconfirmed.json()["error"]["message"]

        too_dear = await client.post(
            "/api/v1/quality/ai-classifier/evaluate", json={"mode": "live", "confirm_calls": 2}
        )
        assert too_dear.json()["error"]["code"] == "AI_BUDGET_TOO_LOW"  # 2 needed, 1 left

    app = create_app(Settings(environment="test", ai_daily_budget=5))
    app.state.database = database
    async with client_for(app, context) as client:
        no_provider = await client.post(
            "/api/v1/quality/ai-classifier/evaluate", json={"mode": "live", "confirm_calls": 2}
        )
        assert no_provider.status_code == 503
    async with client_for(app, context, role="viewer") as viewer:
        forbidden = await viewer.post(
            "/api/v1/quality/ai-classifier/evaluate", json={"mode": "live", "confirm_calls": 2}
        )
        assert forbidden.status_code == 403


async def test_a_confirmed_live_evaluation_runs_paced_counts_its_calls_and_saves_the_score(
    database, workspace_factory, monkeypatch
):
    context = await workspace_factory()
    stub = Stub()
    monkeypatch.setattr(ai_quality, "load_heldout", lambda root: tiny_set(2))
    monkeypatch.setattr(ai_quality, "create_provider", lambda settings: stub)
    app = create_app(Settings(environment="test", ai_daily_budget=5, ai_eval_pause_seconds=0))
    app.state.database = database
    async with client_for(app, context) as client:
        started = await client.post(
            "/api/v1/quality/ai-classifier/evaluate", json={"mode": "live", "confirm_calls": 2}
        )
        assert started.status_code == 200 and started.json()["status"] == "running"

        await asyncio.gather(*app.state.evaluation_tasks)
        latest = (await client.get("/api/v1/quality/ai-classifier")).json()
        run = latest["latest"]
        assert (run["status"], run["source"], run["calls_made"], run["sample_size"]) == (
            "complete", "heldout_live", 2, 2,
        )
        assert run["metrics"]["ai"]["asked"] == 2 and run["metrics"]["ai"]["correct"] == 2
        assert latest["usage"]["used"] == 2 and latest["plan"]["to_call"] == 0  # now answered and cached
        assert stub.calls == 2

        # Nothing left to ask: a further "live" run is free and asks the provider nothing.
        free = await client.post("/api/v1/quality/ai-classifier/evaluate", json={"mode": "live"})
        assert free.status_code == 200 and free.json()["source"] == "heldout_cached" and stub.calls == 2


async def test_only_one_live_evaluation_runs_at_a_time(database, workspace_factory, monkeypatch):
    context = await workspace_factory()
    gate = asyncio.Event()

    class Slow(Stub):
        async def classify(self, subject, body, attachments):
            await gate.wait()
            return await super().classify(subject, body, attachments)

    monkeypatch.setattr(ai_quality, "load_heldout", lambda root: tiny_set(2))
    monkeypatch.setattr(ai_quality, "create_provider", lambda settings: Slow())
    app = create_app(Settings(environment="test", ai_daily_budget=9, ai_eval_pause_seconds=0))
    app.state.database = database
    async with client_for(app, context) as client:
        body = {"mode": "live", "confirm_calls": 2}
        assert (await client.post("/api/v1/quality/ai-classifier/evaluate", json=body)).status_code == 200
        second = await client.post("/api/v1/quality/ai-classifier/evaluate", json=body)
        assert second.status_code == 409 and second.json()["error"]["code"] == "RUN_IN_PROGRESS"
        gate.set()
        await asyncio.gather(*app.state.evaluation_tasks)


async def test_a_rate_limited_live_evaluation_waits_and_retries_instead_of_losing_the_answer(
    database, workspace_factory, monkeypatch
):
    context = await workspace_factory()
    monkeypatch.setattr(ai_quality, "RATE_LIMIT_PAUSE", 0)

    class Limited(Stub):
        """Rate-limits the first two questions to each email, then answers."""

        def __init__(self):
            super().__init__()
            self.refused = {}

        async def classify(self, subject, body, attachments):
            self.refused[subject] = self.refused.get(subject, 0) + 1
            if self.refused[subject] <= 2:
                raise DomainError("PROVIDER_RATE_LIMITED", "quota", retryable=True, status=429)
            return await super().classify(subject, body, attachments)

    provider = Limited()
    monkeypatch.setattr(ai_quality, "load_heldout", lambda root: tiny_set(2))
    monkeypatch.setattr(ai_quality, "create_provider", lambda settings: provider)
    app = create_app(Settings(environment="test", ai_daily_budget=20, ai_eval_pause_seconds=0))
    app.state.database = database
    async with client_for(app, context) as client:
        await client.post("/api/v1/quality/ai-classifier/evaluate", json={"mode": "live", "confirm_calls": 2})
        await asyncio.gather(*app.state.evaluation_tasks)
        run = (await client.get("/api/v1/quality/ai-classifier")).json()["latest"]
    assert run["status"] == "complete" and run["calls_made"] == 2
    assert run["metrics"]["ai"]["asked"] == 2 and run["metrics"]["ai"]["unusable"] == 0  # both got an answer


async def test_the_cached_evaluation_of_the_shipped_heldout_set_matches_the_documented_figures(
    database, workspace_factory
):
    if not ai_quality.HELDOUT.is_dir():
        pytest.skip("the held-out set is not shipped in this environment")
    context = await workspace_factory()
    app = create_app(Settings(environment="test"))
    app.state.database = database
    async with client_for(app, context) as client:
        run = (await client.post("/api/v1/quality/ai-classifier/evaluate", json={"mode": "cached"})).json()
    metrics = run["metrics"]
    assert (run["status"], run["calls_made"], metrics["sample_size"]) == ("complete", 0, 60)
    assert (metrics["rules"]["correct"], metrics["rules"]["abstained"]) == (29, 31)  # rules alone: 48%
    assert (metrics["ai"]["correct"], metrics["ai"]["unusable"]) == (57, 3)  # live AI: 95%, 3 unusable
    assert metrics["combined"]["correct"] == 58


async def test_a_missing_evaluation_set_is_reported_not_faked(database, workspace_factory, monkeypatch):
    context = await workspace_factory()
    monkeypatch.setattr(ai_quality, "load_heldout", lambda root: None)
    app = create_app(Settings(environment="test"))
    app.state.database = database
    async with client_for(app, context) as client:
        body = (await client.get("/api/v1/quality/ai-classifier")).json()
        assert body["available"] is False and body["plan"] is None and body["latest"] is None
        assert (await client.post("/api/v1/quality/ai-classifier/evaluate", json={})).status_code == 404
