import asyncio
import sys
from uuid import uuid4

import httpx
import pytest

from app.ai.grounding import ground_extraction
from app.config import Settings
from app.domain.models import (
    FIELDS,
    Evidence,
    ExtractedField,
    Extraction,
    ParsedDocument,
    SourceBlock,
)

# Tests using default Settings must not load the developer's .env either.
# Explicit _env_file fixture tests still exercise their own temporary files.
Settings.model_config["env_file"] = None


@pytest.fixture(autouse=True)
def forbid_live_http(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Tests must use a mock HTTP transport, never live provider credentials")

    async def forbidden_async(*args, **kwargs):
        forbidden()

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden_async)


@pytest.hookimpl(optionalhook=True)
def pytest_asyncio_loop_factories(config, item):
    if sys.platform == "win32":
        return {"selector": asyncio.SelectorEventLoop}
    return None


@pytest.fixture
def document_factory():
    def build(role="SI", **overrides):
        values = {
            "shipper": "Example Export Ltd",
            "consignee": "Example Import Ltd",
            "notify_party": "Example Import Ltd",
            "port_of_loading": "Port Klang, Malaysia",
            "port_of_discharge": "Singapore",
            "container_count": "3 x 40HC",
            "gross_weight_kg": "22,000 KG",
        }
        values.update(overrides)
        source_id = str(uuid4())
        blocks, fields = [], {}
        for field in FIELDS:
            value = values[field]
            if value is None:
                fields[field] = ExtractedField()
            else:
                block_id = f"{source_id}:{field}"
                blocks.append(
                    SourceBlock(
                        id=block_id,
                        source_id=source_id,
                        text=f"{field.value.replace('_', ' ')}: {value}",
                        locator={"type": "text", "line": len(blocks) + 1},
                    )
                )
                fields[field] = ExtractedField(
                    raw_value=value,
                    state="present",
                    evidence=(Evidence(block_id=block_id, quote=value),),
                )
        extraction = Extraction(document_id=source_id, document_type=role, fields=fields)
        document = ParsedDocument(
            source_id=source_id, sha256="0" * 64, format="txt", blocks=tuple(blocks)
        )
        return extraction, ground_extraction(extraction, document)

    return build
