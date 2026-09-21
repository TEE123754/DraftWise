"""Optional AI extraction that fills fields the labelled-text extractor could not find."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from app.ai.provider import create_provider
from app.config import Settings
from app.domain.models import FIELDS, Extraction, ParsedDocument

logger = logging.getLogger(__name__)


async def _extract(document: ParsedDocument, settings: Settings, ai) -> Extraction:
    # A provider built here is bound to this event loop, so it is also closed here.
    provider = ai if ai is not None else create_provider(settings)
    if provider is None:
        raise LookupError("No AI provider configured")
    try:
        extraction, _ = await asyncio.wait_for(
            provider.extract(document), timeout=settings.ai_timeout_seconds
        )
        return extraction
    finally:
        if ai is None and hasattr(provider, "close"):
            await provider.close()


def _run(coroutine):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    # Called from inside a running loop (e.g. an async API handler): use a private loop.
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coroutine).result()


def fill_missing_with_ai(
    extraction: Extraction, document: ParsedDocument, settings: Settings, ai=None
) -> Extraction:
    """Return the extraction with missing fields filled from the AI provider when it is worth it.

    Only fields the labelled extractor left `missing` are replaced, and only by values the provider
    returns as `present` with evidence that passed grounding. Any provider failure is non-fatal: the
    labelled result is returned unchanged so the pipeline keeps working offline.
    """
    missing = [name for name in FIELDS if extraction.fields[name].state == "missing"]
    if len(missing) < settings.ai_fallback_min_missing:
        return extraction
    try:
        proposed = _run(_extract(document, settings, ai))
    except Exception as exc:  # noqa: BLE001 - provider, network and grounding errors are all non-fatal
        logger.info("AI extraction fallback skipped for %s: %s", document.source_id, exc)
        return extraction
    fields = dict(extraction.fields)
    for name in missing:
        if proposed.fields[name].state == "present":
            fields[name] = proposed.fields[name]
    return extraction.model_copy(update={"fields": fields})
