from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import model_validator

from app.api.dependencies import IdempotencyKey, Operator, Viewer
from app.domain.errors import DomainError
from app.domain.models import StrictModel, VerificationReport
from app.repositories.jobs import accepted, enqueue

router = APIRouter(tags=["verification"])


class VerifyRequest(StrictModel):
    email_id: UUID
    si_extraction_id: UUID | None = None
    bl_extraction_id: UUID | None = None
    policy_version: str = "v1"

    @model_validator(mode="after")
    def coherent_pair(self):
        if (self.si_extraction_id is None) != (self.bl_extraction_id is None):
            raise ValueError("Supply both source revisions or neither")
        if self.si_extraction_id is not None and self.si_extraction_id == self.bl_extraction_id:
            raise ValueError("SI and BL must be different documents")
        if self.policy_version != "v1":
            raise ValueError("Unsupported policy version")
        return self


@router.post("/verify", status_code=202)
async def verify_email(
    body: VerifyRequest,
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
        cursor = await connection.execute(
            "select category,ambiguous from public.email_classifications where workspace_id=%s and email_id=%s order by revision desc limit 1",
            (context.workspace_id, body.email_id),
        )
        classification = await cursor.fetchone()
        if (
            not classification
            or classification["category"] != "BL_COMPARISON"
            or classification["ambiguous"]
        ):
            raise DomainError(
                "CLASSIFICATION_REQUIRED",
                "Confirm this email requests document comparison first",
                status=409,
            )
        for extraction_id, role in ((body.si_extraction_id, "SI"), (body.bl_extraction_id, "BL")):
            if extraction_id:
                cursor = await connection.execute(
                    """select x.document_type from public.document_extractions x join public.attachments a
                    on a.workspace_id=x.workspace_id and a.id=x.attachment_id where x.workspace_id=%s and x.id=%s and a.email_id=%s""",
                    (context.workspace_id, extraction_id, body.email_id),
                )
                extraction = await cursor.fetchone()
                if extraction is None:
                    raise DomainError(
                        "NOT_FOUND", "Source revision was not found for this email", status=404
                    )
                if extraction["document_type"] != role:
                    raise DomainError(
                        "DOCUMENT_ROLE_INVALID",
                        "Source roles must be confirmed before verification",
                    )
        job = await enqueue(
            connection,
            workspace_id=context.workspace_id,
            kind="verify",
            key=key,
            payload=body.model_dump(mode="json") | {"operation": "compare"},
            email_id=body.email_id,
        )
    result = accepted(job)
    response.headers["Location"] = result["status_url"]
    return result


@router.get("/verification/{report_id}", response_model=VerificationReport)
async def get_report(report_id: UUID, request: Request, response: Response, context: Viewer):
    async with request.app.state.database.connection() as connection:
        cursor = await connection.execute(
            "select report,input_fingerprint from public.verification_reports where workspace_id=%s and id=%s",
            (context.workspace_id, report_id),
        )
        row = await cursor.fetchone()
    if row is None:
        raise DomainError("NOT_FOUND", "Verification report was not found", status=404)
    response.headers["ETag"] = f'"{row["input_fingerprint"]}"'
    return row["report"]
