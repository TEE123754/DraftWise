"""The AI classifier's measured score, and the AI budget it is drawn from (P8 and the token policy).

Reading is free. A live evaluation spends provider calls, so it needs an administrator, an exact call
count confirmed by the caller, and enough budget left; it then runs paced in the background. AI answers
are cached by content, so an email that was already answered is never sent again.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Request
from psycopg.types.json import Jsonb
from pydantic import Field

from app.ai.provider import create_provider
from app.api.dependencies import Admin, Viewer
from app.domain.errors import DomainError
from app.domain.models import StrictModel
from app.services.ai_evaluation import load_heldout, score_classifier, usable
from app.services.bounded_ai import BoundedAI, fingerprint, usage

router = APIRouter(tags=["quality"])

HELDOUT = Path(__file__).resolve().parents[3] / "artifacts" / "heldout"
# The same held-out set (emails, categories, saved AI answers), shipped with the application so a
# deployed instance can show its measured score. It holds category labels only, not field values.
SHIPPED_HELDOUT = Path(__file__).resolve().parents[2] / "data" / "heldout"


def heldout_root() -> Path:
    """This checkout's own held-out folder if it has one, otherwise the shipped copy."""
    return HELDOUT if (HELDOUT / "truth.json").is_file() else SHIPPED_HELDOUT
SECONDS_PER_CALL = 13  # measured: one call plus the pause that keeps the provider from rate-limiting
STALE_AFTER = timedelta(minutes=45)
RATE_LIMIT_TRIES = 3
RATE_LIMIT_PAUSE = 30  # seconds; doubles in effect: 30, then 60
RUN_COLUMNS = "id,source,status,sample_size,calls_made,metrics,error,created_at,finished_at"


class Evaluate(StrictModel):
    mode: Literal["cached", "live"] = "cached"
    # A live run must be started with the number the plan showed, so a call count is never a surprise.
    confirm_calls: int = Field(default=0, ge=0, le=1000)


def _remaining(spent: dict) -> int:
    return max(spent["budget"] - spent["used"], 0)


async def _db_answers(connection, workspace_id, settings, emails) -> dict:
    """Answers this workspace already paid for, keyed by email ID, in the same shape as the file cache."""
    model = getattr(settings, f"{settings.ai_provider}_model", "") or ""
    keys = {
        fingerprint(settings.ai_provider, model, "classify", (item.subject, item.body, list(item.attachments))): email_id
        for email_id, item in emails.items()
    }
    rows = await (
        await connection.execute(
            "select cache_key,result,metadata from public.ai_cache where workspace_id=%s and kind='classify' and cache_key=any(%s)",
            (workspace_id, list(keys)),
        )
    ).fetchall()
    return {
        keys[row["cache_key"]]: {
            "category": row["result"]["category"],
            "ambiguous": row["result"]["ambiguous"],
            "seconds": round(row["metadata"].get("latency_ms", 0) / 1000, 1) or None,
        }
        for row in rows
    }


def _answers(file_cache: dict, database_answers: dict) -> dict:
    """File cache first (free, made earlier), then anything the database cache holds."""
    return {**{k: v for k, v in file_cache.items() if usable(v) or "error" in v}, **database_answers}


def _to_call(truth: dict, answers: dict) -> list[str]:
    return sorted(email_id for email_id in truth if not usable(answers.get(email_id)))


async def _expire_stale(connection, workspace_id):
    await connection.execute(
        """update public.quality_runs set status='failed',error='The run stopped before it finished',finished_at=now()
        where workspace_id=%s and kind='ai_classifier' and status='running' and created_at<%s""",
        (workspace_id, datetime.now(UTC) - STALE_AFTER),
    )


@router.get("/quality/ai-usage")
async def ai_usage(request: Request, ctx: Viewer):
    """AI calls used and the allowance they count against (a demo session, or today's workspace budget)."""
    async with request.app.state.database.connection() as connection:
        spent = await usage(connection, ctx.workspace_id, request.app.state.settings)
    return {**spent, "remaining": _remaining(spent)}


@router.get("/quality/ai-classifier")
async def ai_classifier(request: Request, ctx: Viewer):
    settings = request.app.state.settings
    loaded = load_heldout(heldout_root())
    async with request.app.state.database.connection() as connection:
        await _expire_stale(connection, ctx.workspace_id)
        latest = await (
            await connection.execute(
                f"select {RUN_COLUMNS} from public.quality_runs where workspace_id=%s and kind='ai_classifier' order by created_at desc limit 1",
                (ctx.workspace_id,),
            )
        ).fetchone()
        spent = await usage(connection, ctx.workspace_id, settings)
        plan = None
        if loaded:
            truth, emails, file_cache = loaded
            answers = _answers(file_cache, await _db_answers(connection, ctx.workspace_id, settings, emails))
            todo = _to_call(truth, answers)
            plan = {
                "sample_size": len(truth),
                "answered": len(truth) - len(todo),
                "to_call": len(todo),
                "estimated_seconds": len(todo) * SECONDS_PER_CALL,
            }
            if latest is None and len(todo) < len(truth):
                # Nobody has scored this workspace yet, but the saved AI answers make the score free:
                # show it now instead of an empty panel and a button. Nothing is stored (a read
                # never writes) and no AI call is made; "Refresh score" saves a run as before.
                latest = {
                    "id": None,
                    "source": "heldout_cached",
                    "status": "complete",
                    "sample_size": len(truth),
                    "calls_made": 0,
                    "metrics": score_classifier(truth, emails, answers),
                    "error": None,
                    "created_at": None,
                    "finished_at": None,
                }
    return {
        "available": loaded is not None,
        "message": None if loaded else "The labelled evaluation set is not shipped in this environment.",
        "plan": plan,
        "usage": {**spent, "remaining": _remaining(spent)},
        "provider_configured": create_provider(settings) is not None,
        "latest": latest,
    }


async def _finish(database, run_id, workspace_id, loaded, settings, extra_answers, *, calls, status, error=None):
    truth, emails, file_cache = loaded
    async with database.connection() as connection:
        answers = _answers(file_cache, await _db_answers(connection, workspace_id, settings, emails))
        metrics = score_classifier(truth, emails, {**answers, **extra_answers})
        await connection.execute(
            "update public.quality_runs set status=%s,metrics=%s,calls_made=%s,error=%s,finished_at=now() where id=%s",
            (status, Jsonb(metrics), calls, error, run_id),
        )


async def _run_live(app, workspace_id, run_id, loaded, todo):
    settings, database = app.state.settings, app.state.database
    truth, emails, _ = loaded
    provider = create_provider(settings)
    ai = BoundedAI(provider, database, workspace_id, settings)
    made, failures, status, error = 0, {}, "complete", None
    try:
        for email_id in todo:
            email = emails[email_id]
            # The provider client fails fast on a rate limit and nothing durable retries this run, so
            # wait for the quota here, a little longer each time, before giving up on one email.
            for attempt in range(RATE_LIMIT_TRIES):
                try:
                    await ai.classify(email.subject, email.body, list(email.attachments))
                    made += 1
                    break
                except DomainError as exc:
                    if exc.code in {"AI_BUDGET_REACHED", "DEMO_AI_LIMIT"}:
                        status, error = "failed", "The AI budget ran out before every email was asked"
                        break
                    if exc.code == "PROVIDER_RATE_LIMITED" and attempt < RATE_LIMIT_TRIES - 1:
                        await asyncio.sleep(RATE_LIMIT_PAUSE * (attempt + 1))
                        continue
                    failures[email_id] = {"error": exc.code}
                    break
            if status == "failed":
                break
            await asyncio.sleep(settings.ai_eval_pause_seconds)
    except Exception as exc:  # noqa: BLE001 - recorded on the run, never lost
        status, error = "failed", f"{type(exc).__name__}"
    finally:
        await provider.close()
        await _finish(database, run_id, workspace_id, loaded, settings, failures, calls=made, status=status, error=error)


@router.post("/quality/ai-classifier/evaluate", status_code=200)
async def evaluate(body: Evaluate, request: Request, ctx: Admin):
    settings, database = request.app.state.settings, request.app.state.database
    loaded = load_heldout(heldout_root())
    if loaded is None:
        raise DomainError("EVALUATION_SET_UNAVAILABLE", "The labelled evaluation set is not shipped here", status=404)
    truth, emails, file_cache = loaded
    async with database.connection() as connection:
        await _expire_stale(connection, ctx.workspace_id)
        answers = _answers(file_cache, await _db_answers(connection, ctx.workspace_id, settings, emails))
        todo = _to_call(truth, answers)
        spent = await usage(connection, ctx.workspace_id, settings)
        live = body.mode == "live" and bool(todo)
        if live:
            if body.confirm_calls != len(todo):
                raise DomainError(
                    "CONFIRM_CALLS",
                    f"This run needs {len(todo)} AI calls. Send confirm_calls={len(todo)} to start it.",
                    status=409,
                )
            if len(todo) > _remaining(spent):
                raise DomainError(
                    "AI_BUDGET_TOO_LOW", f"{len(todo)} calls needed; {_remaining(spent)} left in the budget", status=409
                )
            if create_provider(settings) is None:
                raise DomainError("PROVIDER_NOT_CONFIGURED", "No AI provider is configured", status=503)
            if await (
                await connection.execute(
                    "select 1 from public.quality_runs where workspace_id=%s and kind='ai_classifier' and status='running'",
                    (ctx.workspace_id,),
                )
            ).fetchone():
                raise DomainError("RUN_IN_PROGRESS", "An evaluation is already running", status=409)
        run = await (
            await connection.execute(
                f"""insert into public.quality_runs(workspace_id,kind,source,status,sample_size,created_by)
                values(%s,'ai_classifier',%s,%s,%s,%s) returning {RUN_COLUMNS}""",
                (ctx.workspace_id, "heldout_live" if live else "heldout_cached", "running" if live else "complete",
                 len(truth), ctx.user_id),
            )
        ).fetchone()
    if not live:
        await _finish(database, run["id"], ctx.workspace_id, loaded, settings, {}, calls=0, status="complete")
        async with database.connection() as connection:
            return await (
                await connection.execute(f"select {RUN_COLUMNS} from public.quality_runs where id=%s", (run["id"],))
            ).fetchone()
    task = asyncio.create_task(_run_live(request.app, ctx.workspace_id, run["id"], loaded, todo))
    tasks = getattr(request.app.state, "evaluation_tasks", None)
    if tasks is None:
        tasks = request.app.state.evaluation_tasks = set()
    tasks.add(task)  # keep a reference so the run is not garbage-collected mid-way
    task.add_done_callback(tasks.discard)
    return run
