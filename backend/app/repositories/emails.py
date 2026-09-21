"""Inbox read model: every email with the facts its review state is derived from."""

from app.services.email_state import EmailFacts, derive_state

# Display ID: the email's own ID when it is short (email_007); otherwise a per-source sequence
# (M-001 for manually added mail). It never depends on the row's position in a list or a filter.
INBOX_SQL = """
with numbered as (
  select e.*, row_number() over (partition by e.source_namespace order by e.created_at, e.id) as seq
  from public.emails e where e.workspace_id=%s
)
select n.id, n.external_id, n.source_namespace,
  case when length(n.external_id) <= 32 then n.external_id
       else upper(left(n.source_namespace, 1)) || '-' || lpad(n.seq::text, 3, '0') end as display_id,
  n.deleted_at, n.deleted_reason, n.subject, n.sender, left(n.body, 300) as body_preview, n.created_at,
  case when c.ambiguous then null else c.category::text end as category,
  c.decided_by as classified_by,
  s.risk_state, coalesce(s.held_for_review, false) as held,
  coalesce(a.attachment_count, 0) as attachment_count,
  coalesce(a.quarantined, 0) as quarantined,
  coalesce(a.unread, 0) as unread,
  coalesce(a.roles, '{}') as roles,
  coalesce(j.active, false) as job_active, j.state as job_state,
  r.status::text as report_status,
  coalesce(r.review_reasons, '{}') as review_reasons,
  coalesce(m.fields, '{}') as mismatch_fields,
  cs.id as case_id, cs.readiness as case_readiness,
  case when c.category = 'BL_COMPARISON' and not c.ambiguous and coalesce(a.attachment_count, 0) = 0
       then left(n.body, 4000) else '' end as body_head
from numbered n
left join lateral (
  select category, ambiguous, decided_by from public.email_classifications
  where workspace_id = n.workspace_id and email_id = n.id order by revision desc limit 1) c on true
left join lateral (
  select risk_state, held_for_review from public.email_safety
  where workspace_id = n.workspace_id and email_id = n.id limit 1) s on true
left join lateral (
  select count(*) as attachment_count,
         count(*) filter (where at.state = 'quarantined') as quarantined,
         count(*) filter (where x.document_type is null) as unread,
         array_agg(x.document_type::text) filter (where x.document_type is not null) as roles
  from public.attachments at
  left join lateral (
    select document_type from public.document_extractions
    where workspace_id = at.workspace_id and attachment_id = at.id order by revision desc limit 1) x on true
  where at.workspace_id = n.workspace_id and at.email_id = n.id and at.state <> 'deleted') a on true
left join lateral (
  select bool_or(state in ('queued', 'running', 'retry_wait')) as active,
         (array_agg(state::text order by created_at desc))[1] as state
  from public.processing_jobs where workspace_id = n.workspace_id and email_id = n.id) j on true
left join lateral (
  select status, review_reasons, report from public.verification_reports
  where workspace_id = n.workspace_id and email_id = n.id order by revision desc limit 1) r on true
left join lateral (
  select array_agg(cmp ->> 'field') as fields
  from jsonb_array_elements(coalesce(r.report -> 'comparisons', '[]'::jsonb)) cmp
  where cmp ->> 'decision' = 'mismatch') m on true
left join public.cases cs on cs.workspace_id = n.workspace_id and cs.email_id = n.id
where (%s::uuid is null or n.id = %s::uuid) and (n.deleted_at is not null) = %s
order by n.created_at desc,
  coalesce(substring(n.external_id from '^(.*?)\\d+$'), n.external_id),
  length(coalesce(substring(n.external_id from '(\\d+)$'), '')),
  coalesce(substring(n.external_id from '(\\d+)$'), ''),
  n.id
"""


def inbox_item(row: dict) -> dict:
    """Combine an email's facts with the state derived from them."""
    roles = tuple(row["roles"])
    facts = EmailFacts(
        category=row["category"],
        risk_state=row["risk_state"],
        held=row["held"],
        attachment_count=row["attachment_count"],
        quarantined=row["quarantined"],
        unread=row["unread"],
        roles=roles,
        job_active=row["job_active"],
        job_state=row["job_state"],
        report_status=row["report_status"],
        mismatch_fields=tuple(row["mismatch_fields"]),
        unresolved_fields=tuple(row["review_reasons"]),
        subject=row["subject"],
        body_head=row["body_head"],
    )
    return {
        "id": row["id"],
        "deleted_at": row["deleted_at"], "deleted_reason": row["deleted_reason"],
        "external_id": row["external_id"],
        "display_id": row["display_id"],
        "subject": row["subject"],
        "sender": row["sender"],
        "body_preview": row["body_preview"],
        "created_at": row["created_at"],
        "category": row["category"],
        "classified_by": row["classified_by"],
        "attachment_count": row["attachment_count"],
        "documents": {
            "count": row["attachment_count"],
            "si": "SI" in roles,
            "bl": "BL" in roles,
            "other": sum(1 for role in roles if role not in ("SI", "BL")),
            "unread": row["unread"],
        },
        "case": {"id": row["case_id"], "readiness": row["case_readiness"]} if row["case_id"] else None,
        "job_state": row["job_state"],
        "job_failed": row["job_state"] == "failed",
        "has_report": row["report_status"] is not None,
        **derive_state(facts).to_dict(),
    }


async def load_field_sources(connection, workspace_id, email_id, extractions):
    """The latest verification report and the SI and BL extraction outputs to show beside it.

    The report's own extractions are used, so the values shown are the ones its decisions were made
    on. A side the report has no extraction for falls back to the newest one of that role.
    """
    report = await (
        await connection.execute(
            """select status,si_extraction_id,bl_extraction_id,report from public.verification_reports
            where workspace_id=%s and email_id=%s order by revision desc limit 1""",
            (workspace_id, email_id),
        )
    ).fetchone()
    by_role = {}
    for row in extractions:
        by_role.setdefault(row["document_type"], row["output"])
    if report is None:
        return None, by_role.get("SI"), by_role.get("BL")
    wanted = [i for i in (report["si_extraction_id"], report["bl_extraction_id"]) if i]
    rows = (
        await (
            await connection.execute(
                "select id,output from public.document_extractions where workspace_id=%s and id = any(%s)",
                (workspace_id, wanted),
            )
        ).fetchall()
        if wanted
        else []
    )
    outputs = {row["id"]: row["output"] for row in rows}
    si = outputs.get(report["si_extraction_id"]) if report["si_extraction_id"] else by_role.get("SI")
    bl = outputs.get(report["bl_extraction_id"]) if report["bl_extraction_id"] else by_role.get("BL")
    return report, si, bl


async def load_inbox(connection, workspace_id, email_id=None, *, trash=False) -> list[dict]:
    """All of the workspace's emails, or just one when `email_id` is given."""
    cursor = await connection.execute(INBOX_SQL, (workspace_id, email_id, email_id, trash))
    return [inbox_item(row) for row in await cursor.fetchall()]
