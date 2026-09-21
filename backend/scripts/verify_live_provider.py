"""Explicit live-provider check on supplied inputs; never loads expected answers."""
import asyncio
import json
import time
from pathlib import Path

from app.ai.provider import create_provider
from app.config import Settings
from app.infrastructure.parsing import parse_bounded
from app.services.dataset_import import open_source


async def main():
    settings = Settings()
    provider = create_provider(settings)
    source = open_source(settings.demo_dataset_path)
    results = []
    try:
        for name in ["email_001_SI.txt", "email_001_BL.txt"]:
            started = time.monotonic()
            try:
                document = await asyncio.to_thread(parse_bounded, source.read("attachments/" + name), name, settings)
                extraction, metadata = await asyncio.wait_for(provider.extract(document), settings.ai_extraction_timeout_seconds)
                result = {"document": name, "state": "success", "metadata": metadata,
                          "present_fields": sum(f.state == "present" for f in extraction.fields.values()),
                          "extraction": extraction.model_dump(mode="json")}
                print(json.dumps({k: v for k, v in result.items() if k != "extraction"}), flush=True)
            except Exception as exc:
                result = {"document": name, "state": "failed", "error": getattr(exc, "code", type(exc).__name__),
                          "elapsed_seconds": round(time.monotonic() - started, 2)}
                print(json.dumps(result), flush=True)
            results.append(result)
    finally:
        source.close()
        if provider:
            await provider.close()
    target = Path(__file__).resolve().parents[2] / "artifacts/quality/live-provider-repair.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return all(r["state"] == "success" for r in results)


if __name__ == "__main__":
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        raise SystemExit(0 if runner.run(main()) else 1)
