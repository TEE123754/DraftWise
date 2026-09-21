import json
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import quality
from app.api.dependencies import Principal, principal
from app.config import Settings
from app.main import create_app


@pytest.fixture
def client_factory():
    def build(**settings):
        app = create_app(Settings(environment="test", **settings))
        app.dependency_overrides[principal] = lambda: Principal(uuid4(), uuid4(), "viewer")
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    return build


async def test_missing_report_is_unavailable_never_placeholder_metrics(
    client_factory, monkeypatch, tmp_path
):
    monkeypatch.setattr(quality, "BENCHMARK_REPORT", tmp_path / "absent.json")
    monkeypatch.setattr(quality, "BENCHMARKS", tmp_path / "no-benchmarks")
    monkeypatch.setattr(quality, "SHIPPED_BENCHMARK_REPORT", tmp_path / "absent-shipped.json")
    monkeypatch.setattr(quality, "SHIPPED_BENCHMARKS", tmp_path / "no-shipped-benchmarks")
    async with client_factory() as client:
        response = await client.get("/api/v1/quality/benchmark")
    assert response.status_code == 404
    assert "accuracy" not in response.text


async def test_corrupt_report_is_unavailable(client_factory, monkeypatch, tmp_path):
    report = tmp_path / "report.json"
    report.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(quality, "BENCHMARK_REPORT", report)
    async with client_factory() as client:
        response = await client.get("/api/v1/quality/benchmark")
    assert response.status_code == 404


async def test_report_without_provenance_is_marked_not_independent(
    client_factory, monkeypatch, tmp_path
):
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"overall": {"accuracy": 0.5}}), encoding="utf-8")
    monkeypatch.setattr(quality, "BENCHMARK_REPORT", report)
    monkeypatch.setattr(quality, "BENCHMARKS", tmp_path / "no-benchmarks")
    monkeypatch.setattr(quality, "SHIPPED_BENCHMARKS", tmp_path / "no-shipped-benchmarks")
    async with client_factory(ai_provider="morpheus", morpheus_model="test-model") as client:
        body = (await client.get("/api/v1/quality/benchmark")).json()
    assert body["reference"]["independent"] is False
    assert body["overall"]["accuracy"] == 0.5
    assert body["official"] is None
    assert body["provider"]["name"] == "morpheus"
    assert body["provider"]["model"] == "test-model"


async def test_official_scoreboard_is_attached_when_present(client_factory, monkeypatch, tmp_path):
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"overall": {"accuracy": 0.5}}), encoding="utf-8")
    run = tmp_path / "organizer-eval-02"
    run.mkdir()
    older = tmp_path / "organizer-eval-01"
    older.mkdir()
    (older / "scoreboard.json").write_text(json.dumps({"final_score": 0.1}), encoding="utf-8")
    (run / "scoreboard.json").write_text(json.dumps({"final_score": 0.6}), encoding="utf-8")
    (run / "manifest.json").write_text(
        json.dumps({"emails_count": 520, "unresolved_classification": ["a", "b"], "ai_fallback": False}),
        encoding="utf-8",
    )
    monkeypatch.setattr(quality, "BENCHMARK_REPORT", report)
    monkeypatch.setattr(quality, "BENCHMARKS", tmp_path)
    monkeypatch.setattr(quality, "SHIPPED_BENCHMARKS", tmp_path / "no-shipped-benchmarks")
    async with client_factory() as client:
        body = (await client.get("/api/v1/quality/benchmark")).json()
    assert body["official"] == {
        "scoreboard": {"final_score": 0.6},
        "run": "organizer-eval-02",
        "emails": 520,
        "unresolved": 2,
        "ai_fallback": False,
    }



async def test_a_deployed_instance_shows_the_shipped_results_when_there_is_no_artifacts_folder(
    client_factory, monkeypatch, tmp_path
):
    # Container images do not include artifacts/. The measured results ship in backend/data instead.
    monkeypatch.setattr(quality, "BENCHMARK_REPORT", tmp_path / "absent.json")
    monkeypatch.setattr(quality, "BENCHMARKS", tmp_path / "no-benchmarks")
    async with client_factory() as client:
        response = await client.get("/api/v1/quality/benchmark")
    assert response.status_code == 200
    official = response.json()["official"]
    assert official["run"] == "organizer-eval-06" and official["emails"] == 520
    assert official["ai_fallback"] is False  # scored on rules alone: no provider calls
    assert official["scoreboard"]["final_score"] == 1.0
    assert official["scoreboard"]["end_to_end"] == {"success": 46, "total": 46, "rate": 1.0}


def test_only_aggregate_results_are_shipped():
    scoreboard = json.loads((quality.SHIPPED_BENCHMARKS / "organizer-eval-06/scoreboard.json").read_text())
    manifest = json.loads((quality.SHIPPED_BENCHMARKS / "organizer-eval-06/manifest.json").read_text())
    assert set(scoreboard) == {"stage1", "stage3", "reliability", "end_to_end", "weights", "final_score", "n_emails"}
    assert "predictions" not in manifest and not (quality.SHIPPED_BENCHMARKS / "organizer-eval-06/submission.json").exists()
    truth = json.loads((quality.DATA / "heldout/truth.json").read_text())
    assert all(set(value) == {"category"} for value in truth.values())  # labels only, no field values
    assert not list(quality.DATA.rglob("ground_truth*"))
