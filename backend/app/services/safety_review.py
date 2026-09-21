from psycopg.types.json import Jsonb

from app.domain.errors import DomainError
from app.services.email_safety import assess_email


async def assess_stored(connection, workspace, email_id):
    # The email and its attachment names come back together: one round trip, not two.
    email = await (
        await connection.execute(
            """select e.sender,e.subject,e.body,
            coalesce(array_agg(a.original_name order by a.original_name)
                     filter (where a.original_name is not null), '{}') as names
            from public.emails e left join public.attachments a
            on a.workspace_id=e.workspace_id and a.email_id=e.id
            where e.workspace_id=%s and e.id=%s and e.deleted_at is null group by e.id""",
            (workspace, email_id),
        )
    ).fetchone()
    if not email:
        raise DomainError("NOT_FOUND", "Email was not found", status=404)
    result = assess_email(
        email["sender"], None, email["subject"], email["body"], list(email["names"])
    ).to_dict()
    row = await (
        await connection.execute(
            """insert into public.email_safety(workspace_id,email_id,risk_state,severity,signals,held_for_review)
        values(%s,%s,%s,%s,%s,%s) on conflict(email_id) do update set
        risk_state=excluded.risk_state,severity=excluded.severity,signals=excluded.signals,
        held_for_review=case when email_safety.released_at is null then excluded.held_for_review else false end,
        assessed_at=now() returning *""",
            (
                workspace,
                email_id,
                result["risk_state"],
                result["severity"],
                Jsonb(result["signals"]),
                result["held_for_review"],
            ),
        )
    ).fetchone()
    if row["risk_state"] in {"suspected_phishing", "spam"}:
        await connection.execute(
            """insert into public.drift_alerts(workspace_id,alert_type,severity,title,description,sample_email_ids)
            select %s,%s,%s,%s,%s,%s where not exists(select 1 from public.drift_alerts
            where workspace_id=%s and alert_type in ('spam','phishing') and sample_email_ids @> %s)""",
            (
                workspace,
                "phishing" if row["risk_state"] == "suspected_phishing" else "spam",
                row["severity"],
                "Email safety review",
                "; ".join(s["description"] for s in result["signals"]),
                Jsonb([str(email_id)]),
                workspace,
                Jsonb([str(email_id)]),
            ),
        )
    return row


async def require_safe(connection, workspace, email_id):
    row = await assess_stored(connection, workspace, email_id)
    if row["held_for_review"]:
        raise DomainError(
            "SAFETY_REVIEW_REQUIRED",
            "A reviewer must release this email before document processing",
            status=409,
        )
