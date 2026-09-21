import asyncio
import hashlib
import random
import time

from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from app.ai.grounding import strict_json
from app.ai.structured import StructuredClient
from app.config import Settings
from app.domain.errors import DomainError


class GeminiClient(StructuredClient):
    def __init__(self, settings: Settings, client=None):
        if not settings.gemini_api_key and client is None:
            raise DomainError(
                "PROVIDER_NOT_CONFIGURED",
                "Configure GEMINI_API_KEY to enable AI extraction",
                status=503,
            )
        self.settings = settings
        self.client = client or genai.Client(
            api_key=settings.gemini_api_key.get_secret_value(),
            http_options=types.HttpOptions(timeout=60_000),
        )
        self.semaphore = asyncio.Semaphore(settings.provider_concurrency)

    async def close(self):
        await self.client.aio.aclose()

    async def _generate(self, prompt: str, schema: dict, model_class):
        if len(prompt) > self.settings.max_prompt_chars:
            raise DomainError(
                "PROVIDER_INPUT_LIMIT", "Document requires chunking before AI extraction"
            )
        started = time.monotonic()
        for attempt in range(3):
            try:
                async with self.semaphore:
                    response = await self.client.aio.models.generate_content(
                        model=self.settings.gemini_model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0,
                            response_mime_type="application/json",
                            response_json_schema=schema,
                        ),
                    )
                if not response.text:
                    raise DomainError(
                        "PROVIDER_REFUSAL", "Provider returned no usable structured output"
                    )
                result = model_class.model_validate(strict_json(response.text))
                metadata = {
                    "provider": "gemini",
                    "model": self.settings.gemini_model,
                    "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                    "schema_version": "v1",
                    "latency_ms": round((time.monotonic() - started) * 1000),
                    "attempt": attempt + 1,
                }
                if response.usage_metadata:
                    metadata["usage"] = response.usage_metadata.model_dump(exclude_none=True)
                return result, metadata
            except errors.APIError as exc:
                if exc.code == 429:
                    # Durable worker chooses the retry time; no tight in-process quota retry.
                    raise DomainError(
                        "PROVIDER_RATE_LIMITED",
                        "AI quota is temporarily unavailable",
                        retryable=True,
                        status=429,
                    ) from exc
                if exc.code not in {500, 502, 503, 504} or attempt == 2:
                    raise DomainError(
                        "PROVIDER_UNAVAILABLE",
                        "AI provider is unavailable",
                        retryable=exc.code >= 500,
                        status=503,
                    ) from exc
                await asyncio.sleep(random.uniform(0.5, 2 ** (attempt + 1)))
            except (ValidationError, ValueError) as exc:
                raise DomainError(
                    "PROVIDER_OUTPUT_INVALID", "AI output did not satisfy the extraction contract"
                ) from exc
