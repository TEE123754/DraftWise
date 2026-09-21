from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import Field, model_validator

from app.api.dependencies import IdempotencyKey, Operator, Viewer
from app.domain.errors import DomainError
from app.domain.models import StrictModel
from app.repositories.jobs import accepted, enqueue

router = APIRouter(tags=["extraction"])


class ExtractRequest(StrictModel):
    attachment_ids: tuple[UUID, ...] = Field(min_length=1, max_length=20)
    role_hints: dict[UUID, Literal["SI", "BL", "UNKNOWN"]] = Field(default_factory=dict)
    reprocess: bool = False

    @model_validator(mode="after")
    def unique_ids(self):
        if len(set(self.attachment_ids)) != len(self.attachment_ids) or not set(
            self.role_hints
        ) <= set(self.attachment_ids):
            raise ValueError("Attachment IDs must be unique and cover every role hint")
        return self


@router.post("/extract", status_code=202)
async def extract(
    body: ExtractRequest,
    request: Request,
    response: Response,
    context: Operator,
    key: IdempotencyKey,
):
    async with request.app.state.database.connection() as connection:
        cursor = await connection.execute(
            "select id,state from public.attachments where workspace_id=%s and id=any(%s)",
            (context.workspace_id, list(body.attachment_ids)),
        )
        rows = await cursor.fetchall()
        if len(rows) != len(body.attachment_ids):
            raise DomainError("NOT_FOUND", "One or more attachments were not found", status=404)
        if any(row["state"] != "validated" for row in rows):
            raise DomainError(
                "UPLOAD_PENDING", "Complete the uploads before extraction", status=409
            )
        job = await enqueue(
            connection,
            workspace_id=context.workspace_id,
            kind="extract",
            key=key,
            payload=body.model_dump(mode="json"),
        )
    result = accepted(job)
    response.headers["Location"] = result["status_url"]
    return result


@router.get("/extractions/{extraction_id}")
async def get_extraction(extraction_id: UUID, request: Request, context: Viewer):
    async with request.app.state.database.connection() as connection:
        cursor = await connection.execute(
            "select id,revision,output from public.document_extractions where workspace_id=%s and id=%s",
            (context.workspace_id, extraction_id),
        )
        row = await cursor.fetchone()
    if row is None:
        raise DomainError("NOT_FOUND", "Extraction was not found", status=404)
    return row
