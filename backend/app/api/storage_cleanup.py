"""Administrator view of uploaded files queued for deletion after Trash, and a retry for ones that failed."""

from uuid import UUID

from fastapi import APIRouter, Request

from app.api.dependencies import Admin
from app.domain.errors import DomainError

router = APIRouter(tags=["storage"])

STATES = ("pending", "deleted", "skipped", "failed")


def _item(row):
    return {
        "id": str(row["id"]),
        "storage_key": row["storage_key"],
        "file_name": row["storage_key"].rsplit("/", 1)[-1],
        "state": row["state"],
        "attempts": row["attempts"],
        "last_error": row["last_error"],
        "next_attempt_at": row["next_attempt_at"].isoformat() if row["next_attempt_at"] else None,
        "created_at": row["created_at"].isoformat(),
        "finished_at": row["finished_at"].isoformat() if row["finished_at"] else None,
    }


@router.get("/storage-cleanup")
async def list_cleanup(request: Request, context: Admin):
    """Counts by state, plus every file that failed and every pending one that has already had an error."""
    async with request.app.state.database.connection() as connection:
        counts = await (
            await connection.execute(
                "select state,count(*) as n from public.storage_cleanup where workspace_id=%s group by state",
                (context.workspace_id,),
            )
        ).fetchall()
        rows = await (
            await connection.execute(
                """select id,storage_key,state,attempts,last_error,next_attempt_at,created_at,finished_at
                from public.storage_cleanup
                where workspace_id=%s and (state='failed' or (state='pending' and attempts>0))
                order by case state when 'failed' then 0 else 1 end, created_at desc limit 100""",
                (context.workspace_id,),
            )
        ).fetchall()
    by_state = dict.fromkeys(STATES, 0) | {row["state"]: row["n"] for row in counts}
    return {
        "by_state": by_state,
        "storage_configured": request.app.state.settings.supabase_service_role_key is not None
        and bool(request.app.state.settings.supabase_url),
        "items": [_item(row) for row in rows],
    }


@router.post("/storage-cleanup/{item_id}/retry")
async def retry_cleanup(item_id: UUID, request: Request, context: Admin):
    """Put a failed deletion back in the queue with a fresh set of attempts; the worker picks it up next."""
    async with request.app.state.database.connection() as connection:
        row = await (
            await connection.execute(
                """update public.storage_cleanup set state='pending',attempts=0,last_error=null,
                next_attempt_at=now(),finished_at=null
                where id=%s and workspace_id=%s and state='failed'
                returning id,storage_key,state,attempts,last_error,next_attempt_at,created_at,finished_at""",
                (item_id, context.workspace_id),
            )
        ).fetchone()
        if row is None:
            exists = await (
                await connection.execute(
                    "select state from public.storage_cleanup where id=%s and workspace_id=%s",
                    (item_id, context.workspace_id),
                )
            ).fetchone()
            if exists is None:
                raise DomainError("NOT_FOUND", "That file is not in the deletion queue", status=404)
            raise DomainError("NOT_FAILED", "Only a failed deletion can be retried", status=409)
    return _item(row)
