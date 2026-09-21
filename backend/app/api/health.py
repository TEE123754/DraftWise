from fastapi import APIRouter, Request

from app.domain.errors import DomainError
from app.infrastructure.hosting import hosting_kind

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {"status": "ok", "version": "pipeline-v1"}


def worker_verdict(api_kind: str, counts: dict[str, int]) -> str | None:
    """Why this API cannot process jobs, or None when it can.

    A deployed API needs a deployed worker: workers on other machines that share the database keep
    the queue moving only while those machines stay on, and must not make the service look healthy.
    """
    if sum(counts.values()) == 0:
        return "The processing worker is not active"
    if api_kind == "hosted" and counts.get("hosted", 0) == 0:
        return (
            "No worker is running in the deployed service; only workers on other machines are "
            "processing jobs"
        )
    return None


@router.get("/ready")
async def ready(request: Request):
    async with request.app.state.database.connection() as connection:
        await connection.execute("select 1")
        cursor = await connection.execute(
            """select kind, count(*) as slots from public.worker_heartbeats
            where last_seen > now()-interval '60 seconds' group by kind"""
        )
        counts = {row["kind"]: row["slots"] for row in await cursor.fetchall()}
    problem = worker_verdict(hosting_kind(), counts)
    if problem:
        raise DomainError("WORKER_UNAVAILABLE", problem, retryable=True, status=503)
    # `workers` counts live worker slots by where they run, so a laptop worker is visible as such.
    return {
        "status": "ready",
        "database": "ok",
        "worker": "active",
        "workers": {kind: counts.get(kind, 0) for kind in ("hosted", "local", "unknown")},
    }
