"""Remove expired Trash records; keep audit and independent benchmark history."""
from psycopg import sql

from app.services.storage_cleanup import physical_keys, queue_unreferenced


async def purge_trash(connection):
    emails=await (await connection.execute("""select id,workspace_id from public.emails
        where deleted_at<now()-interval '30 days' order by deleted_at limit 25 for update skip locked""")).fetchall()
    for email in emails:
        workspace,email_id=email["workspace_id"],email["id"]
        cases="select id from public.cases where workspace_id=%s and email_id=%s"
        reports="select id from public.verification_reports where workspace_id=%s and email_id=%s"
        attachments="select id from public.attachments where workspace_id=%s and email_id=%s"
        extractions=f"select id from public.document_extractions where workspace_id=%s and attachment_id in ({attachments})"
        scopes=[
            ("issue_events","issue_id",f"select id from public.case_issues where workspace_id=%s and case_id in ({cases})",3),
            *[(t,"case_id",cases,2) for t in ("amendment_drafts","correction_previews","evidence_dependencies","case_actions","case_issues","amendment_rounds","case_documents")],
            ("review_actions","review_id","select id from public.review_queue where workspace_id=%s and email_id=%s",2),
            ("report_rule_applications","report_id",reports,2),
            ("discrepancies","report_id",reports,2),
            *[(t,"extraction_id",extractions,3) for t in ("anomalies","normalized_fields")],
            ("job_events","job_id","select id from public.processing_jobs where workspace_id=%s and email_id=%s",2),
        ]
        # Scope parameter tuples are explicit, never values interpolated into SQL.
        for table,column,subquery,levels in scopes:
            args=(workspace,)*(levels-1)+(workspace,email_id)
            await connection.execute(sql.SQL("delete from public.{} where workspace_id=%s and {} in (").format(sql.Identifier(table),sql.Identifier(column))+sql.SQL(subquery)+sql.SQL(")"),args)
        for table in ("email_workflows","cases","review_queue","verification_reports","email_safety","email_classifications","processing_jobs"):
            await connection.execute(sql.SQL("delete from public.{} where workspace_id=%s and email_id=%s").format(sql.Identifier(table)),(workspace,email_id))
        for table in ("document_extractions","source_blocks","document_references","document_links"):
            await connection.execute(sql.SQL("delete from public.{} where workspace_id=%s and attachment_id in (").format(sql.Identifier(table))+sql.SQL(attachments)+sql.SQL(")"),(workspace,workspace,email_id))
        # Uploaded object keys are retained for an administrator's storage cleanup.
        await connection.execute("""insert into public.audit_logs(workspace_id,actor_type,action,entity_type,entity_id,request_id,details)
            select %s,'system','trash_purged','email',%s,gen_random_uuid(),jsonb_build_object('uploaded_storage_keys',coalesce(jsonb_agg(storage_key) filter(where storage_key not like 'demo-seed/%%'),'[]'::jsonb))
            from public.attachments where workspace_id=%s and email_id=%s""",(workspace,email_id,workspace,email_id))
        keys=await physical_keys(connection,workspace,email_id)
        await connection.execute("delete from public.attachments where workspace_id=%s and email_id=%s",(workspace,email_id))
        await connection.execute("delete from public.emails where workspace_id=%s and id=%s",(workspace,email_id))
        # The uploaded bytes are deleted by the worker (retrying), unless a linked document still uses them.
        await queue_unreferenced(connection,workspace,keys)
    return len(emails)
