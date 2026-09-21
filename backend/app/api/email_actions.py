from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import Field, field_validator

from app.api.dependencies import Operator
from app.domain.errors import DomainError
from app.domain.models import StrictModel
from app.services.email_actions import record_action, trash_email

router=APIRouter(tags=["email actions"])


class Reason(StrictModel):
    reason: str = Field(min_length=5,max_length=1000)
    @field_validator("reason")
    @classmethod
    def meaningful(cls,value):
        if len(value.strip())<5:
            raise ValueError("Give a review reason")
        return value.strip()


class BulkTrash(Reason):
    email_ids: list[UUID] = Field(min_length=1,max_length=100)


@router.delete("/emails/{email_id}")
async def trash(email_id:UUID,body:Reason,request:Request,ctx:Operator):
    async with request.app.state.database.connection() as conn:
        await trash_email(conn,ctx,email_id,body.reason)
    return {"state":"trashed"}


@router.post("/emails/trash")
async def bulk_trash(body:BulkTrash,request:Request,ctx:Operator):
    async with request.app.state.database.connection() as conn:
        for email_id in sorted(set(body.email_ids)):
            await trash_email(conn,ctx,email_id,body.reason)
    return {"state":"trashed","count":len(set(body.email_ids))}


@router.post("/emails/{email_id}/restore")
async def restore(email_id:UUID,body:Reason,request:Request,ctx:Operator):
    async with request.app.state.database.connection() as conn:
        row=await (await conn.execute("select deleted_at from public.emails where workspace_id=%s and id=%s for update",(ctx.workspace_id,email_id))).fetchone()
        if not row:
            raise DomainError("NOT_FOUND","Email was not found",status=404)
        result=await conn.execute("""update public.emails set deleted_at=null,deleted_by=null,deleted_reason=null
            where workspace_id=%s and id=%s and deleted_at>now()-interval '30 days'""",(ctx.workspace_id,email_id))
        if result.rowcount != 1:
            raise DomainError("RESTORE_UNAVAILABLE","The email is not in Trash or its 30-day restore period expired",status=409)
        await record_action(conn,ctx,"email_restored",email_id,{"reason":body.reason})
    return {"state":"restored","next_action":"Review before restarting processing"}
