from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import Field

from app.api.dependencies import Operator, Viewer
from app.domain.errors import DomainError
from app.domain.models import StrictModel
from app.repositories.jobs import project_job_state

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}")
async def get_job(job_id: UUID, request: Request, context: Viewer):
    async with request.app.state.database.connection() as connection:
        cursor = await connection.execute(
            "select id,state,kind as stage,attempt,result,error_code,updated_at from public.processing_jobs where workspace_id=%s and id=%s",
            (context.workspace_id, job_id),
        )
        job = await cursor.fetchone()
    if job is None:
        raise DomainError("NOT_FOUND", "Job was not found", status=404)
    return job


class RetryRequest(StrictModel):
    reason: str = Field(min_length=1, max_length=1000)


@router.post("/jobs/{job_id}/retry", status_code=202)
async def retry_job(job_id: UUID, body: RetryRequest, request: Request, context: Operator):
    async with request.app.state.database.connection() as connection:
        cursor = await connection.execute(
            """update public.processing_jobs set state='queued',available_at=now(),updated_at=now(),
            max_attempts=least(10,max_attempts+1) where workspace_id=%s and id=%s and state='failed' and attempt<10 returning *""",
            (context.workspace_id, job_id),
        )
        job = await cursor.fetchone()
        if job is None:
            raise DomainError("RETRY_UNAVAILABLE", "Job is not available for retry", status=409)
        await project_job_state(connection, job, "checking")
        await connection.execute(
            "insert into public.job_events(workspace_id,job_id,stage,event) values(%s,%s,'retry',jsonb_build_object('actor_id',%s::text,'reason',%s::text))",
            (context.workspace_id, job_id, str(context.user_id), body.reason),
        )
    return {"job_id": job_id, "state": "queued", "status_url": f"/api/v1/jobs/{job_id}"}
