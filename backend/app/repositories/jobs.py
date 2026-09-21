import hashlib
import json
from uuid import UUID

from psycopg.types.json import Jsonb

from app.domain.errors import DomainError


def digest(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


async def enqueue(
    connection,
    *,
    workspace_id: UUID,
    kind: str,
    key: str,
    payload: dict,
    email_id: UUID | None = None,
):
    request_hash = digest(payload)
    cursor = await connection.execute(
        """insert into public.processing_jobs(workspace_id,email_id,kind,idempotency_key,request_sha256,payload)
        values(%s,%s,%s,%s,%s,%s) on conflict(workspace_id,kind,idempotency_key) do nothing returning *""",
        (workspace_id, email_id, kind, key, request_hash, Jsonb(payload)),
    )
    job = await cursor.fetchone()
    if job is None:
        cursor = await connection.execute(
            "select * from public.processing_jobs where workspace_id=%s and kind=%s and idempotency_key=%s",
            (workspace_id, kind, key),
        )
        job = await cursor.fetchone()
        if job["request_sha256"] != request_hash:
            raise DomainError(
                "IDEMPOTENCY_CONFLICT",
                "This request key was already used with different inputs",
                status=409,
            )
    return job


async def claim(connection):
    cursor = await connection.execute("""with candidate as (
        select id from public.processing_jobs where state in ('queued','retry_wait') and available_at<=now() and attempt<max_attempts
        order by (kind <> 'verify'),available_at,created_at for update skip locked limit 1)
        update public.processing_jobs j set state='running',attempt=attempt+1,lease_token=gen_random_uuid(),
        leased_until=now()+interval '90 seconds',updated_at=now() from candidate c where j.id=c.id returning j.*""")
    return await cursor.fetchone()


async def recover(connection):
    cursor = await connection.execute("""update public.processing_jobs set
        state=case when attempt<max_attempts then 'retry_wait'::public.job_status else 'failed'::public.job_status end,
        available_at=now()+interval '30 seconds',lease_token=null,leased_until=null,
        error_code='WORKER_LEASE_EXHAUSTED',updated_at=now() where state='running' and leased_until<now() returning *""")
    for job in await cursor.fetchall():
        if job["state"] == "failed":
            await project_job_state(connection, job, "failed")


async def project_job_state(connection, job, readiness):
    payload = job["payload"]
    if job["kind"] != "verify" or not payload.get("case_id"):
        return
    await connection.execute(
        """update public.cases set readiness=%s,updated_at=now()
        where workspace_id=%s and id=%s and version=%s and readiness in ('checking','failed')
        and active_si_id is not distinct from %s::uuid and active_bl_id is not distinct from %s::uuid""",
        (
            readiness,
            job["workspace_id"],
            UUID(payload["case_id"]),
            payload["case_version"],
            payload.get("si_extraction_id"),
            payload.get("bl_extraction_id"),
        ),
    )


async def fail(connection, job, error):
    state = "retry_wait" if error.retryable and job["attempt"] < job["max_attempts"] else "failed"
    delay = 300 if error.code == "PROVIDER_RATE_LIMITED" else min(300, 30 * 2 ** job["attempt"])
    cursor = await connection.execute(
        """update public.processing_jobs set state=%s,error_code=%s,lease_token=null,leased_until=null,
        available_at=now()+(%s * interval '1 second'),updated_at=now()
        where workspace_id=%s and id=%s and lease_token=%s and state='running' and leased_until>now() returning id""",
        (state, error.code, delay, job["workspace_id"], job["id"], job["lease_token"]),
    )
    if await cursor.fetchone() is not None and state == "failed":
        await project_job_state(connection, job, "failed")


async def fence(connection, job):
    cursor = await connection.execute(
        """select id from public.processing_jobs where workspace_id=%s and id=%s and
        state='running' and lease_token=%s and leased_until>now() for update""",
        (job["workspace_id"], job["id"], job["lease_token"]),
    )
    if await cursor.fetchone() is None:
        raise DomainError("JOB_LEASE_LOST", "A newer worker owns this job", status=409)


async def finish(connection, job, result: dict):
    await fence(connection, job)
    await connection.execute(
        """update public.processing_jobs set state='succeeded',result=%s,lease_token=null,
        leased_until=null,error_code=null,updated_at=now() where workspace_id=%s and id=%s""",
        (Jsonb(result), job["workspace_id"], job["id"]),
    )
    await connection.execute(
        "insert into public.job_events(workspace_id,job_id,stage,event) values(%s,%s,%s,%s)",
        (job["workspace_id"], job["id"], job["kind"], Jsonb({"state": "succeeded"})),
    )


def accepted(job):
    return {
        "job_id": str(job["id"]),
        "state": job["state"],
        "status_url": f"/api/v1/jobs/{job['id']}",
    }
