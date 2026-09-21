"""Durable chaining reuses the same classify/extract/verify handlers for all intake."""

from psycopg.types.json import Jsonb

from app.repositories.jobs import enqueue
from app.services.safety_review import assess_stored


async def start_workflow(connection, workspace, email_id, key, prefer_ai=True):
    safety = await assess_stored(connection, workspace, email_id)
    if safety["held_for_review"]:
        await connection.execute(
            """insert into public.email_workflows(workspace_id,email_id,state,details)
            values(%s,%s,'held',%s) on conflict(workspace_id,email_id) do update set
            state='held',details=excluded.details,updated_at=now()""",
            (
                workspace,
                email_id,
                Jsonb({"next_action": "Review safety signals before processing"}),
            ),
        )
        return {"state": "held", "email_id": str(email_id)}
    existing = await (
        await connection.execute(
            """select w.*,j.state as job_state from public.email_workflows w
        left join public.processing_jobs j on j.workspace_id=w.workspace_id and j.id=w.job_id
        where w.workspace_id=%s and w.email_id=%s for update of w""",
            (workspace, email_id),
        )
    ).fetchone()
    if existing and existing["job_state"] in {"queued", "running", "retry_wait"}:
        return {
            "state": existing["state"],
            "job_id": str(existing["job_id"]),
            "email_id": str(email_id),
        }
    job = await enqueue(
        connection,
        workspace_id=workspace,
        kind="classify",
        key=key,
        email_id=email_id,
        payload={"workflow": True, "prefer_ai": prefer_ai},
    )
    await connection.execute(
        """insert into public.email_workflows(workspace_id,email_id,state,job_id)
        values(%s,%s,'classifying',%s) on conflict(workspace_id,email_id) do update set
        state='classifying',job_id=excluded.job_id,details='{}',updated_at=now()""",
        (workspace, email_id, job["id"]),
    )
    return {"state": "classifying", "job_id": str(job["id"]), "email_id": str(email_id)}


async def workflow_state(connection, job, state, details, next_job=None, case_id=None):
    await connection.execute(
        """update public.email_workflows set state=%s,details=%s,
        job_id=%s,case_id=coalesce(%s,case_id),updated_at=now() where workspace_id=%s and email_id=%s""",
        (
            state,
            Jsonb(details),
            next_job["id"] if next_job else job["id"],
            case_id,
            job["workspace_id"],
            job["email_id"],
        ),
    )
