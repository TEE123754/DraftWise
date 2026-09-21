"""Batch AI-assisted email classifier benchmark runner."""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv

load_dotenv(str(BACKEND_DIR / ".env"), override=True)

from app.ai.provider import create_provider
from app.config import get_settings
from app.services.classification import classify_explicit
from app.services.dataset_import import open_source

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("classifier_benchmark")


async def run_benchmark(limit: int | None = None, bundle_path: str | None = None):
    settings = get_settings()
    bundle = bundle_path or settings.demo_dataset_path or str(BASE_DIR / "sdoc-hackathon-bundle.zip")
    logger.info("Opening dataset bundle from: %s", bundle)

    source = open_source(bundle)
    emails = source.emails()
    if limit:
        emails = emails[:limit]
    logger.info("Loaded %d emails to classify", len(emails))

    out_dir = BASE_DIR / "artifacts/benchmarks/ai-classifier-run-01"
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "predictions.jsonl"

    provider = None
    try:
        provider = create_provider(settings)
        logger.info("Live AI provider initialized: %s (%s)", settings.ai_provider, getattr(settings, f"{settings.ai_provider}_model", "default"))
    except Exception as exc:
        logger.warning("AI provider could not be initialized (%s); will use rule-only with fallback", exc)

    stats = {
        "total": len(emails),
        "rule_resolved": 0,
        "ai_resolved": 0,
        "fallback": 0,
        "errors": 0,
    }

    started = time.monotonic()
    with open(jsonl_path, "w", encoding="utf-8") as out_file:
        for idx, em in enumerate(emails, 1):
            eid = em.email_id
            subject = em.subject or ""
            body = em.body or ""
            att_names = [a if isinstance(a, str) else getattr(a, "original_name", str(a)) for a in em.attachments]

            # 1. Deterministic high-precision rules
            rule_res = classify_explicit(subject, body)
            if rule_res is not None:
                record = {
                    "email_id": eid,
                    "category": rule_res.category,
                    "method": "rule",
                    "confidence": 0.98 if not rule_res.ambiguous else 0.65,
                    "reason_code": rule_res.reason_code,
                    "ambiguous": rule_res.ambiguous,
                }
                stats["rule_resolved"] += 1
            elif provider is not None:
                # 2. AI-assisted classification with retry & rate limiting
                ai_record = None
                for attempt in range(3):
                    try:
                        ai_res, metadata = await asyncio.wait_for(
                            provider.classify(subject, body, att_names),
                            timeout=settings.ai_timeout_seconds,
                        )
                        ai_record = {
                            "email_id": eid,
                            "category": ai_res.category,
                            "method": "ai",
                            "confidence": 0.88 if not ai_res.ambiguous else 0.60,
                            "reason_code": ai_res.reason_code,
                            "ambiguous": ai_res.ambiguous,
                            "metadata": {
                                "provider": metadata.get("provider"),
                                "latency_ms": metadata.get("latency_ms"),
                            },
                        }
                        stats["ai_resolved"] += 1
                        break
                    except Exception as exc:
                        if attempt < 2:
                            await asyncio.sleep(1.0 * (attempt + 1))
                        else:
                            logger.debug("AI classify failed for %s: %s", eid, exc)
                if ai_record:
                    record = ai_record
                else:
                    record = {
                        "email_id": eid,
                        "category": "GENERAL",
                        "method": "fallback",
                        "confidence": 0.50,
                        "reason_code": "conflicting_intent",
                        "ambiguous": True,
                    }
                    stats["fallback"] += 1
            else:
                record = {
                    "email_id": eid,
                    "category": "GENERAL",
                    "method": "fallback",
                    "confidence": 0.50,
                    "reason_code": "conflicting_intent",
                    "ambiguous": True,
                }
                stats["fallback"] += 1

            out_file.write(json.dumps(record) + "\n")
            out_file.flush()

            if idx % 25 == 0 or idx == len(emails):
                logger.info(
                    "Progress: %d/%d (Rules: %d, AI: %d, Fallback: %d)",
                    idx,
                    len(emails),
                    stats["rule_resolved"],
                    stats["ai_resolved"],
                    stats["fallback"],
                )

    elapsed = round(time.monotonic() - started, 2)
    stats["elapsed_seconds"] = elapsed
    stats["throughput_eps"] = round(len(emails) / max(elapsed, 0.01), 2)

    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    logger.info("Classifier benchmark completed in %ss. Summary written to %s", elapsed, summary_path)

    if provider:
        await provider.close()
    source.close()
    return stats


if __name__ == "__main__":
    limit_arg = int(sys.argv[1]) if len(sys.argv) > 1 else None
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(run_benchmark(limit=limit_arg))
