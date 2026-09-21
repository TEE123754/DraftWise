import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from uuid import UUID, uuid4

from fastapi import APIRouter, Request
from pydantic import Field

from app.api.dependencies import Operator, Viewer
from app.domain.errors import DomainError
from app.domain.models import StrictModel
from app.infrastructure.parsing import parse_bounded
from app.services.email_actions import active_email

router = APIRouter(tags=["uploads"])
MIMES = {
    "txt": "text/plain",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


class ReserveUpload(StrictModel):
    email_id: UUID
    filename: str = Field(min_length=1, max_length=240)
    mime_type: str
    byte_size: int = Field(gt=0, le=20 * 1024 * 1024)


class CompleteUpload(StrictModel):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


@router.post("/uploads", status_code=201)
async def reserve(body: ReserveUpload, request: Request, context: Operator):
    if body.mime_type not in MIMES.values():
        raise DomainError("FILE_UNSUPPORTED", "Use TXT, PDF, DOCX or XLSX documents", status=415)
    attachment_id = uuid4()
    storage_key = f"{context.workspace_id}/{attachment_id}"
    async with request.app.state.database.connection() as connection:
        cursor = await connection.execute(
            "select id from public.emails where workspace_id=%s and id=%s and deleted_at is null for update",
            (context.workspace_id, body.email_id),
        )
        if await cursor.fetchone() is None:
            raise DomainError("NOT_FOUND", "Email was not found", status=404)
        cursor = await connection.execute(
            "select count(*) as total from public.attachments where workspace_id=%s and email_id=%s and state<>'deleted'",
            (context.workspace_id, body.email_id),
        )
        if (await cursor.fetchone())["total"] >= 20:
            raise DomainError("UPLOAD_LIMIT", "This email already has 20 attachments", status=413)
        await connection.execute(
            """insert into public.attachments(id,workspace_id,email_id,original_name,storage_key,mime_type,byte_size)
            values(%s,%s,%s,%s,%s,%s,%s)""",
            (
                attachment_id,
                context.workspace_id,
                body.email_id,
                PurePosixPath(body.filename.replace("\\", "/")).name,
                storage_key,
                body.mime_type,
                body.byte_size,
            ),
        )
    upload_url = await request.app.state.storage.reserve(storage_key)
    return {
        "attachment_id": attachment_id,
        "upload_url": upload_url,
        "expires_at": datetime.now(UTC) + timedelta(hours=2),
    }


@router.post("/uploads/{attachment_id}/complete")
async def complete(attachment_id: UUID, body: CompleteUpload, request: Request, context: Operator):
    async with request.app.state.database.connection() as connection:
        cursor = await connection.execute(
            "select * from public.attachments where workspace_id=%s and id=%s",
            (context.workspace_id, attachment_id),
        )
        attachment = await cursor.fetchone()
        if attachment is not None:
            await active_email(connection, context.workspace_id, attachment["email_id"])
    if attachment is None:
        raise DomainError("NOT_FOUND", "Upload was not found", status=404)
    if attachment["state"] == "validated":
        if attachment["sha256"] != body.sha256:
            raise DomainError(
                "HASH_MISMATCH",
                "This upload has already been finalized with different content",
                status=409,
            )
        return {"attachment_id": attachment_id, "state": "validated"}
    if attachment["state"] != "pending":
        raise DomainError("UPLOAD_UNAVAILABLE", "This upload cannot be finalized", status=409)
    data = await request.app.state.storage.download(attachment["storage_key"])
    if len(data) != attachment["byte_size"] or hashlib.sha256(data).hexdigest() != body.sha256:
        raise DomainError(
            "HASH_MISMATCH", "Uploaded bytes do not match the reserved file", status=409
        )
    async with request.app.state.parser_semaphore:
        parsed = await asyncio.to_thread(
            parse_bounded, data, str(attachment_id), request.app.state.settings
        )
    if MIMES[parsed.format] != attachment["mime_type"]:
        raise DomainError(
            "FILE_UNSUPPORTED", "Document signature does not match its declared format", status=415
        )
    async with request.app.state.database.connection() as connection:
        await active_email(connection, context.workspace_id, attachment["email_id"], lock=True)
        cursor = await connection.execute(
            "update public.attachments set state='validated',sha256=%s where workspace_id=%s and id=%s and state='pending' returning id",
            (body.sha256, context.workspace_id, attachment_id),
        )
        if await cursor.fetchone() is None:
            raise DomainError(
                "UPLOAD_CHANGED", "Upload state changed; refresh before retrying", status=409
            )
    return {"attachment_id": attachment_id, "state": "validated"}


@router.get("/attachments/{attachment_id}/preview")
async def preview(attachment_id: UUID, request: Request, context: Viewer):
    async with request.app.state.database.connection() as connection:
        cursor = await connection.execute(
            """select a.id from public.attachments a join public.emails e on e.workspace_id=a.workspace_id and e.id=a.email_id
            where a.workspace_id=%s and a.id=%s and a.state='validated' and e.deleted_at is null""",
            (context.workspace_id, attachment_id),
        )
        if await cursor.fetchone() is None:
            raise DomainError("NOT_FOUND", "Document was not found", status=404)
        cursor = await connection.execute(
            "select id,text_content,locator,quality from public.source_blocks where workspace_id=%s and attachment_id=%s order by ordinal limit 5000",
            (context.workspace_id, attachment_id),
        )
        return {"blocks": await cursor.fetchall(), "locator_type": "source_blocks"}
