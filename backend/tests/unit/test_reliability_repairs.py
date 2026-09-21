import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from psycopg import OperationalError

from app.ai.extraction_contract import Candidate, ExtractionCandidate, expand_candidate
from app.ai.grounding import ground_extraction
from app.config import Settings
from app.domain.errors import DomainError
from app.domain.models import FIELDS, ParsedDocument, SourceBlock
from app.workers import runner


def test_test_settings_ignore_live_environment(monkeypatch):
    monkeypatch.setenv("MORPHEUS_API_KEY", "should-not-load")
    monkeypatch.setenv("DEMO_ENABLED", "true")
    settings = Settings(environment="test")
    assert settings.morpheus_api_key is None
    assert settings.demo_enabled is False


def test_bundle_path_is_relative_to_backend(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    path = Settings(environment="test", demo_dataset_path="../samples.zip").demo_dataset_path
    assert Path(path) == Path(__file__).resolve().parents[3] / "samples.zip"


def test_compact_extraction_expands_only_cited_source():
    document = ParsedDocument(source_id="source", sha256="0" * 64, format="txt", blocks=(
        SourceBlock(id="block", source_id="source", text="Shipper: Acme", locator={}),
    ))
    fields = {name: Candidate() for name in FIELDS}
    fields[FIELDS[0]] = Candidate(value="Acme", blocks=(0,))
    output = expand_candidate(ExtractionCandidate(document_type="SI", fields=fields), document)
    assert output.fields[FIELDS[0]].evidence[0].quote == "Shipper: Acme"
    ground_extraction(output, document)
    fields[FIELDS[0]] = Candidate(value="Invented", blocks=(0,))
    with pytest.raises(DomainError):
        ground_extraction(expand_candidate(ExtractionCandidate(document_type="SI", fields=fields), document), document)
    fields[FIELDS[0]] = Candidate(value="Acme", blocks=(999,))
    with pytest.raises(DomainError):
        expand_candidate(ExtractionCandidate(document_type="SI", fields=fields), document)


async def test_worker_recovers_and_preserves_cancellation(monkeypatch):
    @asynccontextmanager
    async def connection():
        yield None
    database = SimpleNamespace(connection=connection)
    poll = AsyncMock(side_effect=[OperationalError("disconnected"), OperationalError("offline"), None, asyncio.CancelledError()])
    sleeps = AsyncMock()
    monkeypatch.setattr(runner, "poll_once", poll)
    monkeypatch.setattr(runner, "purge_expired_samples", AsyncMock())
    monkeypatch.setattr(runner.asyncio, "sleep", sleeps)
    with pytest.raises(asyncio.CancelledError):
        await runner.serve(database, None, "worker")
    assert [call.args[0] for call in sleeps.await_args_list] == [1, 2]
    assert poll.await_count == 4
