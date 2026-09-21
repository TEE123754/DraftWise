from uuid import uuid4

from psycopg.types.json import Jsonb

from app.domain.errors import DomainError


async def record_action(connection, ctx, action, email_id, details):
    await connection.execute("""insert into public.audit_logs(workspace_id,actor_id,actor_type,action,entity_type,entity_id,request_id,details)
        values(%s,%s,'user',%s,%s,%s,%s,%s)""",
        (ctx.workspace_id,ctx.user_id,action,"alert" if action.startswith("alert_") else "email",email_id,uuid4(),Jsonb(details)))


async def active_email(connection, workspace, email_id, *, lock=False):
    row = await (await connection.execute(
        "select * from public.emails where workspace_id=%s and id=%s and deleted_at is null" + (" for update" if lock else ""),
        (workspace,email_id))).fetchone()
    if not row:
        raise DomainError("NOT_FOUND", "Email is unavailable or in Trash", status=404)
    return row


async def trash_email(connection, ctx, email_id, reason):
    row = await (await connection.execute("select * from public.emails where workspace_id=%s and id=%s for update",(ctx.workspace_id,email_id))).fetchone()
    if not row:
        raise DomainError("NOT_FOUND","Email was not found",status=404)
    category = await (await connection.execute("select category from public.email_classifications where workspace_id=%s and email_id=%s order by revision desc limit 1",(ctx.workspace_id,email_id))).fetchone()
    if ctx.role not in {"reviewer","admin"} and (not category or category["category"] != "SPAM"):
        raise DomainError("FORBIDDEN","A reviewer must approve removal of non-spam email",status=403)
    if row["deleted_at"]:
        return
    await connection.execute("update public.emails set deleted_at=now(),deleted_by=%s,deleted_reason=%s where workspace_id=%s and id=%s",(ctx.user_id,reason,ctx.workspace_id,email_id))
    # Fence in-flight workers and remove queued work; restore never resumes AI silently.
    await connection.execute("""update public.processing_jobs set state='failed',error_code='EMAIL_TRASHED',lease_token=null,leased_until=null
        where workspace_id=%s and (email_id=%s or payload->>'email_id'=%s or
        (kind='extract' and payload->'attachment_ids' ?| array(select id::text from public.attachments where workspace_id=%s and email_id=%s)))
        and state in ('queued','running','retry_wait')""",(ctx.workspace_id,email_id,str(email_id),ctx.workspace_id,email_id))
    await record_action(connection,ctx,"email_trashed",email_id,{"reason":reason})


async def relabel_release(connection, ctx, email_id, category, reason):
    await active_email(connection,ctx.workspace_id,email_id,lock=True)
    await connection.execute("""insert into public.email_classifications(workspace_id,email_id,revision,category,ambiguous,confidence,decided_by,evidence,run_metadata)
        select %s,%s,coalesce(max(revision),0)+1,%s,false,1,'human','[]',%s from public.email_classifications where workspace_id=%s and email_id=%s""",
        (ctx.workspace_id,email_id,category,Jsonb({"method":"human_review","reason":reason,"reviewer_id":str(ctx.user_id)}),ctx.workspace_id,email_id))
    if category != "SPAM":
        await connection.execute("update public.email_safety set held_for_review=false,reviewed_by=%s,released_at=now(),release_reason=%s where workspace_id=%s and email_id=%s",(ctx.user_id,reason,ctx.workspace_id,email_id))
    await record_action(connection,ctx,"email_reviewed",email_id,{"category":category,"reason":reason})
