"""Every live AI call goes through here: cached by content, counted, and stopped at the budget.

Token policy: rules run first everywhere else. When AI is asked for, an identical input is never sent
twice (the cache), a demo session may make a handful of calls, and any other workspace may make
`ai_daily_budget` calls a day. Past either limit the caller falls back to the rules.
"""

import asyncio
import hashlib
import json

from psycopg.types.json import Jsonb

from app.domain.errors import DomainError
from app.domain.models import Extraction
from app.services.classification import Classification

# Only these answers are cached; each is rebuilt into its own model on a hit.
CACHED = {"classify": ("classify", Classification), "extract": ("extract", Extraction)}


def _plain(value):
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def fingerprint(provider: str, model: str, method: str, args) -> str:
    """Same provider, model, question and input give the same key."""
    body = json.dumps([provider, model, method, [_plain(a) for a in args]], sort_keys=True, default=str)
    return hashlib.sha256(body.encode()).hexdigest()


async def usage(connection, workspace_id, settings) -> dict:
    """What has been spent, and out of what: a demo session's allowance, or today's workspace budget."""
    demo = await (
        await connection.execute(
            "select ai_calls from public.demo_sessions where workspace_id=%s", (workspace_id,)
        )
    ).fetchone()
    if demo:
        return {
            "scope": "demo_session",
            "used": demo["ai_calls"],
            "budget": settings.demo_ai_call_limit if settings.demo_ai_enabled else 0,
        }
    row = await (
        await connection.execute(
            "select calls from public.ai_usage where workspace_id=%s and day=current_date", (workspace_id,)
        )
    ).fetchone()
    return {"scope": "day", "used": row["calls"] if row else 0, "budget": settings.ai_daily_budget}


class BoundedAI:
    def __init__(self, provider, database, workspace, settings):
        self.provider, self.database, self.workspace, self.settings = (
            provider,
            database,
            workspace,
            settings,
        )

    def _key(self, method, args):
        model = getattr(self.settings, f"{self.settings.ai_provider}_model", "") or ""
        return fingerprint(self.settings.ai_provider, model, method, args)

    async def _cached(self, method, key):
        if method not in CACHED:
            return None
        async with self.database.connection() as connection:
            row = await (
                await connection.execute(
                    "select result,metadata from public.ai_cache where workspace_id=%s and cache_key=%s",
                    (self.workspace, key),
                )
            ).fetchone()
        if row is None:
            return None
        model_class = CACHED[method][1]
        return model_class.model_validate(row["result"]), {**row["metadata"], "cache": "hit"}

    async def _store(self, method, key, result):
        if method not in CACHED:
            return
        answer, metadata = result
        async with self.database.connection() as connection:
            await connection.execute(
                """insert into public.ai_cache(workspace_id,cache_key,kind,result,metadata) values(%s,%s,%s,%s,%s)
                on conflict do nothing""",
                (self.workspace, key, method, Jsonb(answer.model_dump(mode="json")), Jsonb(metadata)),
            )

    async def _reserve(self):
        """Count one call against the allowance that applies, or refuse it."""
        async with self.database.connection() as connection:
            row = await (
                await connection.execute(
                    "select * from public.demo_sessions where workspace_id=%s for update",
                    (self.workspace,),
                )
            ).fetchone()
            if row:
                allowed = await (
                    await connection.execute(
                        """update public.demo_sessions set ai_calls=ai_calls+1
                    where workspace_id=%s and expires_at>now() and ai_calls<%s returning ai_calls""",
                        (
                            self.workspace,
                            self.settings.demo_ai_call_limit if self.settings.demo_ai_enabled else 0,
                        ),
                    )
                ).fetchone()
                if not allowed:
                    raise DomainError("DEMO_AI_LIMIT", "Demo AI allowance reached; using rules")
                return
            budget = self.settings.ai_daily_budget
            allowed = budget > 0 and await (
                await connection.execute(
                    """insert into public.ai_usage(workspace_id,day,calls) values(%s,current_date,1)
                    on conflict(workspace_id,day) do update set calls=public.ai_usage.calls+1
                    where public.ai_usage.calls<%s returning calls""",
                    (self.workspace, budget),
                )
            ).fetchone()
            if not allowed:
                raise DomainError("AI_BUDGET_REACHED", "Today's AI budget is used up; using rules")

    async def call(self, method, *args):
        key = self._key(method, args)
        cached = await self._cached(method, key)
        if cached is not None:
            return cached
        await self._reserve()
        try:
            result = await asyncio.wait_for(
                getattr(self.provider, method)(*args),
                self.settings.ai_extraction_timeout_seconds
                if method == "extract" else self.settings.ai_timeout_seconds,
            )
        except TimeoutError:
            raise DomainError("AI_TIMEOUT", "AI timed out; using rules") from None
        await self._store(method, key, result)
        return result

    async def classify(self, *args):
        return await self.call("classify", *args)

    async def extract(self, *args):
        return await self.call("extract", *args)
