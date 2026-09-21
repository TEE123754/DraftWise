from fastapi import APIRouter, Request

from app.domain.errors import DomainError

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {"status": "ok", "version": "pipeline-v1"}


@router.get("/ready")
async def ready(request: Request):
    async with request.app.state.database.connection() as connection:
        await connection.execute("select 1")
        cursor = await connection.execute(
            "select exists(select 1 from public.worker_heartbeats where last_seen > now()-interval '60 seconds') as active"
        )
        active = (await cursor.fetchone())["active"]
    if not active:
        raise DomainError(
            "WORKER_UNAVAILABLE", "The processing worker is not active", retryable=True, status=503
        )
    return {"status": "ready", "database": "ok", "worker": "active"}
