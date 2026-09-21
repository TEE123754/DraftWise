"""Monitoring uses reviewed baselines and two disjoint windows; no fabricated baseline."""

from psycopg.types.json import Jsonb

from app.repositories.jobs import digest
from app.services.quality import assess_windows


async def monitor(connection, workspace):
    baseline = await (
        await connection.execute(
            "select * from public.quality_baselines where workspace_id=%s", (workspace,)
        )
    ).fetchone()
    if not baseline:
        return assess_windows(None, [], [])
    rows = await (
        await connection.execute(
            """select e.id,c.category,c.created_at from public.emails e
        join lateral(select category,created_at from public.email_classifications where workspace_id=e.workspace_id
        and email_id=e.id and not ambiguous and decided_by<>'human' order by revision desc limit 1)c on true
        where e.workspace_id=%s and c.created_at>%s order by c.created_at desc,e.id limit 40""",
            (workspace, baseline["created_at"]),
        )
    ).fetchall()
    rows = list(reversed(rows))
    result = assess_windows(
        baseline["reference_data"]["distribution"],
        [r["category"] for r in rows[:20]],
        [r["category"] for r in rows[20:]],
    )
    result.update(
        baseline_version=baseline["version"], sample_email_ids=[str(r["id"]) for r in rows[-5:]]
    )
    reviewed = await (
        await connection.execute(
            """select h.category as expected,p.category as predicted from
        (select distinct on(email_id) * from public.email_classifications where workspace_id=%s and decided_by='human' and created_at>%s order by email_id,revision desc)h
        join lateral(select category from public.email_classifications where workspace_id=h.workspace_id and email_id=h.email_id
        and revision<h.revision and decided_by<>'human' order by revision desc limit 1)p on true""",
            (workspace, baseline["created_at"]),
        )
    ).fetchall()
    result["reviewed_sample_count"] = len(reviewed)
    result["reviewed_error_rate"] = (
        sum(r["expected"] != r["predicted"] for r in reviewed) / len(reviewed) if reviewed else None
    )
    result["baseline_error_rate"] = baseline["reference_data"].get("error_rate")
    result["reviewed_error_change"] = (
        (result["reviewed_error_rate"] - result["baseline_error_rate"])
        if result["reviewed_error_rate"] is not None and result["baseline_error_rate"] is not None
        else None
    )
    if result["state"] == "suspected_shift":
        fingerprint = digest({"ids": sorted(str(r["id"]) for r in rows)})
        inserted = await (
            await connection.execute(
                """insert into public.quality_windows(workspace_id,baseline_version,fingerprint,result)
            values(%s,%s,%s,%s) on conflict do nothing returning id""",
                (workspace, baseline["version"], fingerprint, Jsonb(result)),
            )
        ).fetchone()
        if inserted:
            await connection.execute(
                """insert into public.drift_alerts(workspace_id,alert_type,severity,title,description,baseline_version,sample_email_ids,changed_features,affected_window_start,affected_window_end)
                values(%s,'drift','medium','Sustained classification distribution shift',%s,%s,%s,%s,%s,%s)""",
                (
                    workspace,
                    "Two independent 20-email windows differ from the reviewed baseline. Investigate; concept drift is not confirmed.",
                    baseline["version"],
                    Jsonb(result["sample_email_ids"]),
                    Jsonb([result]),
                    rows[0]["created_at"],
                    rows[-1]["created_at"],
                ),
            )
    return result
