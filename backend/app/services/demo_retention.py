"""Bound sample storage without changing immutable audit records or real workspaces."""

from psycopg import sql

# Child-first, explicit allowlist; new tables must be reviewed before inclusion.
SAMPLE_TABLES = (
    "ai_cache", "ai_usage", "quality_runs", "document_references", "conversations", "dashboard_preferences", "quality_windows", "quality_baselines",
    "drift_alerts", "email_safety", "email_workflows", "gmail_messages", "mailbox_connections",
    "amendment_drafts", "correction_previews", "evidence_dependencies", "case_actions",
    "issue_events", "case_issues", "amendment_rounds", "case_documents", "cases",
    "report_rule_applications", "rule_evaluations", "equivalence_rules", "customers",
    "review_actions", "review_queue", "discrepancies", "verification_reports",
    "anomalies", "normalized_fields", "document_extractions", "source_blocks",
    "document_links", "shipments", "job_events", "processing_jobs",
    "benchmark_predictions", "benchmark_runs", "attachments", "email_classifications", "emails",
)


async def purge_expired_samples(connection):
    # Same lock as provisioning; concurrent requests cannot bypass the capacity cap.
    await connection.execute("select pg_advisory_xact_lock(84291731)")
    sessions = await (await connection.execute("""
        select d.workspace_id from public.demo_sessions d
        where d.purged_at is null and d.expires_at < now()-interval '2 minutes'
        and not exists(select 1 from public.memberships m
            where m.workspace_id=d.workspace_id and m.user_id<>d.actor_id)
        and not exists(select 1 from public.attachments a
            where a.workspace_id=d.workspace_id and a.storage_key not like 'demo-seed/%%')
        and not exists(select 1 from public.processing_jobs j
            where j.workspace_id=d.workspace_id and j.state='running' and j.leased_until>now())
        order by d.expires_at limit 20 for update of d
    """)).fetchall()
    workspaces = [row["workspace_id"] for row in sessions]
    if not workspaces:
        return 0
    for table in SAMPLE_TABLES:
        if table in {"conversations", "gmail_messages", "mailbox_connections"}:
            present = await (await connection.execute(
                "select to_regclass(%s) as name", ("public." + table,),
            )).fetchone()
            if present["name"] is None:
                continue
        await connection.execute(
            sql.SQL("delete from public.{} where workspace_id=any(%s)").format(sql.Identifier(table)),
            (workspaces,),
        )
    await connection.execute(
        "update public.demo_sessions set purged_at=now() where workspace_id=any(%s)", (workspaces,),
    )
    return len(sessions)
