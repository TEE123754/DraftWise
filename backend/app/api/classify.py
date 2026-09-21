from uuid import UUID

from fastapi import APIRouter, Request, Response

from app.api.dependencies import IdempotencyKey, Operator
from app.domain.errors import DomainError
from app.domain.models import StrictModel
from app.repositories.jobs import accepted, enqueue

router = APIRouter(tags=["classification"])


class ClassifyRequest(StrictModel):
    email_id: UUID
    reprocess: bool = False


@router.post("/classify", status_code=202)
async def classify(
    body: ClassifyRequest,
    request: Request,
    response: Response,
    context: Operator,
    key: IdempotencyKey,
):
    async with request.app.state.database.connection() as connection:
        cursor = await connection.execute(
            "select id from public.emails where workspace_id=%s and id=%s",
            (context.workspace_id, body.email_id),
        )
        if await cursor.fetchone() is None:
            raise DomainError("NOT_FOUND", "Email was not found", status=404)
        job = await enqueue(
            connection,
            workspace_id=context.workspace_id,
            kind="classify",
            key=key,
            payload=body.model_dump(mode="json"),
            email_id=body.email_id,
        )
    result = accepted(job)
    response.headers["Location"] = result["status_url"]
    return result
