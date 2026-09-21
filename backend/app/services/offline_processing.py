"""Read and compare documents for a whole mailbox with local rules only.

Nothing here can call an AI provider: every job is queued with `prefer_ai: False`, so the
workers' labelled parser, comparison engine and the extract -> case -> verify chain do the work
for free. AI stays an explicit, budgeted choice made per email.

Queueing is a handful of statements however many emails there are: a hosted database costs
~100 ms per round trip, and this runs while a person waits for the demo to open.
"""

from psycopg.types.json import Jsonb

from app.repositories.jobs import digest

# Comparison emails that have documents nobody has read yet, and no job already running for them,
# with the IDs of their (validated) attachments.
ELIGIBLE_SQL = """
select e.id, (array_agg(a.id order by a.id))[1:20] as attachment_ids
from public.emails e
join lateral (
  select category, ambiguous from public.email_classifications
  where workspace_id = e.workspace_id and email_id = e.id order by revision desc limit 1) c on true
left join lateral (
  select held_for_review from public.email_safety
  where workspace_id = e.workspace_id and email_id = e.id limit 1) s on true
join public.attachments a on a.workspace_id = e.workspace_id and a.email_id = e.id and a.state = 'validated'
where e.deleted_at is null and e.workspace_id = %s and (%s::uuid is null or e.id = %s::uuid)
  and c.category = 'BL_COMPARISON' and not c.ambiguous
  and not coalesce(s.held_for_review, false)
  and not exists (
    select 1 from public.processing_jobs j
    where j.workspace_id = e.workspace_id and j.email_id = e.id
      and j.state in ('queued', 'running', 'retry_wait'))
group by e.id, e.created_at, e.external_id
having bool_or(not exists (
    select 1 from public.document_extractions x
    where x.workspace_id = a.workspace_id and x.attachment_id = a.id))
order by e.created_at,
  coalesce(substring(e.external_id from '^(.*?)\\d+$'), e.external_id),
  length(coalesce(substring(e.external_id from '(\\d+)$'), '')),
  coalesce(substring(e.external_id from '(\\d+)$'), ''),
  e.id
"""

# Jobs are created in one statement, so they would all share one timestamp and be claimed in
# arbitrary order. `seq` spaces them a millisecond apart so the mailbox is read in inbox order
# (email_001 first): the first emails a visitor opens are the first ones to be checked.
CREATE_JOBS_SQL = """
insert into public.processing_jobs(workspace_id,email_id,kind,idempotency_key,request_sha256,payload,created_at)
select %s, x.email_id, 'extract', x.key, x.sha, x.payload, now() + x.seq * interval '1 millisecond'
from jsonb_to_recordset(%s) as x(email_id uuid, key text, sha text, payload jsonb, seq int)
on conflict(workspace_id,kind,idempotency_key) do nothing
returning id, email_id
"""

EXISTING_JOBS_SQL = """
select email_id, state::text as state from public.processing_jobs
where workspace_id = %s and kind = 'extract' and idempotency_key = any(%s)
"""

WORKFLOWS_SQL = """
insert into public.email_workflows(workspace_id,email_id,state,job_id,details)
select %s, x.email_id, 'extracting', x.job_id, %s
from jsonb_to_recordset(%s) as x(email_id uuid, job_id uuid)
on conflict(workspace_id,email_id) do update set
  state='extracting', job_id=excluded.job_id, details=excluded.details, updated_at=now()
"""


async def queue_offline_processing(connection, workspace_id, email_id=None) -> dict:
    """Queue rules-only reading (and, through the workflow chain, comparison) of unread documents."""
    emails = await (await connection.execute(ELIGIBLE_SQL, (workspace_id, email_id, email_id))).fetchall()
    if not emails:
        return {"queued": 0, "skipped_failed": 0}
    requests = []
    for seq, email in enumerate(emails):
        attachment_ids = [str(value) for value in email["attachment_ids"]]
        payload = {"attachment_ids": attachment_ids, "workflow": True, "prefer_ai": False, "offline": True}
        requests.append(
            {
                "email_id": str(email["id"]),
                "key": f"offline:{email['id']}:{digest({'attachments': attachment_ids})[:12]}",
                "sha": digest(payload),
                "payload": payload,
                "seq": seq,
            }
        )
    created = await (await connection.execute(CREATE_JOBS_SQL, (workspace_id, Jsonb(requests)))).fetchall()
    if created:
        await connection.execute(
            WORKFLOWS_SQL,
            (
                workspace_id,
                Jsonb({"next_action": "Reading the documents"}),
                Jsonb([{"email_id": str(row["email_id"]), "job_id": str(row["id"])} for row in created]),
            ),
        )
    made = {row["email_id"] for row in created}
    left_out = [request for request in requests if request["email_id"] not in {str(e) for e in made}]
    skipped_failed = 0
    if left_out:
        # The same request already exists: if it failed, a person decides whether to retry it.
        existing = await (
            await connection.execute(EXISTING_JOBS_SQL, (workspace_id, [r["key"] for r in left_out]))
        ).fetchall()
        skipped_failed = sum(1 for row in existing if row["state"] in ("failed", "cancelled"))
    return {"queued": len(created), "skipped_failed": skipped_failed}
