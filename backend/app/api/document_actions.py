from uuid import UUID,uuid4
from fastapi import APIRouter,Request
from psycopg.types.json import Jsonb
from app.api.dependencies import Operator,Viewer,IdempotencyKey
from app.api.email_actions import Reason
from app.domain.errors import DomainError
from app.repositories.emails import load_inbox
from app.repositories.jobs import enqueue
from app.services.email_actions import active_email,record_action
from app.services.references import suggestions
from app.services.safety_review import require_safe

router=APIRouter(tags=["document actions"])


def document_actions(item):
    codes={r["code"] for r in item["reasons"]}
    missing=[name for role,name in [("si","shipping instructions"),("bl","draft bill of lading")] if not item["documents"][role]]
    kind=item["action"]["kind"]
    comparison_required=item.get("category","BL_COMPARISON")=="BL_COMPARISON"
    if not comparison_required:
        missing=[]
    if "unreadable" in codes: request="Please resend a readable copy of the shipping documents."
    elif "wrong_doc_type" in codes: request="Please send the correct "+" and ".join(missing)+" for this shipment."
    elif kind=="resend": request="The attachments mentioned in your email did not arrive. Please resend the shipping instructions and draft bill of lading."
    elif kind=="await_draft": request="Please send the draft bill of lading when available so we can review it with the shipping instructions."
    elif missing: request="Please send the "+" and ".join(missing)+" for this shipment."
    else: request="Please confirm the attached shipping documents are the latest revisions for this shipment."
    return {"missing":missing,"kind":kind,"title":item["action"]["title"],"reasons":item["reasons"],
            "draft_reply":f"Hello,\n\n{request}\n\nRegarding: {item['subject']}\n\nThank you.",
            "can_request":comparison_required and bool(missing or "unreadable" in codes),"comparison_required":comparison_required,"method":"local_template"}


@router.get("/emails/{email_id}/document-actions")
async def actions(email_id:UUID,request:Request,ctx:Viewer):
    async with request.app.state.database.connection() as conn:
        email=await active_email(conn,ctx.workspace_id,email_id)
        item=(await load_inbox(conn,ctx.workspace_id,email_id))[0]
        return {**document_actions(item),"references":await suggestions(conn,ctx.workspace_id,email)}


class LinkDocument(Reason):
    attachment_id: UUID


@router.post("/emails/{email_id}/link-document",status_code=202)
async def link_document(email_id:UUID,body:LinkDocument,request:Request,ctx:Operator,key:IdempotencyKey):
    async with request.app.state.database.connection() as conn:
        email=await active_email(conn,ctx.workspace_id,email_id,lock=True)
        await require_safe(conn,ctx.workspace_id,email_id)
        candidates=await suggestions(conn,ctx.workspace_id,email)
        if body.attachment_id not in {r["attachment_id"] for r in candidates["suggestions"]}:
            raise DomainError("LINK_UNSUPPORTED","Select a document with an exact supported reference in this workspace",status=409)
        source=await (await conn.execute("select * from public.attachments where workspace_id=%s and id=%s",(ctx.workspace_id,body.attachment_id))).fetchone()
        await active_email(conn,ctx.workspace_id,source["email_id"],lock=True)
        await require_safe(conn,ctx.workspace_id,source["email_id"])
        existing=await (await conn.execute("select id from public.attachments where workspace_id=%s and email_id=%s and metadata->>'linked_from'=%s",(ctx.workspace_id,email_id,str(body.attachment_id)))).fetchone()
        attachment_id=existing["id"] if existing else uuid4()
        if not existing:
            count=await (await conn.execute("select count(*) as n from public.attachments where workspace_id=%s and email_id=%s and state<>'deleted'",(ctx.workspace_id,email_id))).fetchone()
            if count["n"]>=20: raise DomainError("ATTACHMENT_LIMIT","Maximum 20 attachments per email",status=409)
            await conn.execute("""insert into public.attachments(id,workspace_id,email_id,original_name,storage_key,mime_type,byte_size,sha256,state,metadata)
                values(%s,%s,%s,%s,%s,%s,%s,%s,'validated',%s)""",
                (attachment_id,ctx.workspace_id,email_id,source["original_name"],f"linked-source/{ctx.workspace_id}/{attachment_id}/{source['storage_key']}",source["mime_type"],source["byte_size"],source["sha256"],Jsonb({"linked_from":str(body.attachment_id),"reason":body.reason})))
            await record_action(conn,ctx,"document_linked",email_id,{"source":str(body.attachment_id),"reason":body.reason})
        ids=await (await conn.execute("select id from public.attachments where workspace_id=%s and email_id=%s and state='validated'",(ctx.workspace_id,email_id))).fetchall()
        job=await enqueue(conn,workspace_id=ctx.workspace_id,email_id=email_id,kind="extract",key=key,
            payload={"attachment_ids":[str(r["id"]) for r in ids],"workflow":True,"prefer_ai":False})
        await conn.execute("""insert into public.email_workflows(workspace_id,email_id,state,job_id) values(%s,%s,'extracting',%s)
            on conflict(workspace_id,email_id) do update set state='extracting',job_id=excluded.job_id,updated_at=now()""",(ctx.workspace_id,email_id,job["id"]))
    return {"job_id":job["id"],"attachment_id":attachment_id}
