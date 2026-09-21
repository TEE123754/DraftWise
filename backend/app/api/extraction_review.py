from uuid import UUID, uuid4

from fastapi import APIRouter, Request
from psycopg.types.json import Jsonb
from pydantic import Field

from app.ai.grounding import ground_extraction
from app.api.cases import SelectSources, select_sources_transaction
from app.api.dependencies import IdempotencyKey, Reviewer
from app.domain.errors import DomainError
from app.domain.models import (
    ExtractedField,
    Extraction,
    FieldName,
    ParsedDocument,
    SourceBlock,
    StrictModel,
)
from app.repositories.cases import audit, get_case, require_version
from app.repositories.jobs import digest
from app.services.safety_review import require_safe

router = APIRouter(tags=["review"])


class FieldReview(StrictModel):
    expected_version: int = Field(ge=1)
    field: FieldName
    value: ExtractedField
    reason: str = Field(min_length=5, max_length=1000)


@router.post("/cases/{case_id}/extractions/{extraction_id}/review", status_code=202)
async def review_field(case_id: UUID, extraction_id: UUID, body: FieldReview,
                       request: Request, context: Reviewer, key: IdempotencyKey):
    async with request.app.state.database.connection() as connection:
        case = await get_case(connection, context.workspace_id, case_id, lock=True)
        request_hash = digest({"source": extraction_id, **body.model_dump(mode="json")})
        # Repeated network delivery must not create multiple revisions.
        existing = await (await connection.execute(
            "select * from public.processing_jobs where workspace_id=%s and kind='verify' and idempotency_key=%s",
            (context.workspace_id, key),
        )).fetchone()
        if existing:
            review = await (await connection.execute(
                "select run_metadata from public.document_extractions where workspace_id=%s and run_metadata->>'review_key'=%s",
                (context.workspace_id, key),
            )).fetchone()
            if not review or review["run_metadata"].get("request_hash") != request_hash:
                raise DomainError("IDEMPOTENCY_CONFLICT", "Review key already used", status=409)
            return {"job_id": existing["id"], "case_id": case_id, "case_version": existing["payload"]["case_version"]}
        require_version(case, body.expected_version)
        if extraction_id not in {case["active_si_id"], case["active_bl_id"]}:
            raise DomainError("STALE_REVIEW", "Select the active document before reviewing it", status=409)
        await require_safe(connection, context.workspace_id, case["email_id"])
        old = await (await connection.execute(
            "select * from public.document_extractions where workspace_id=%s and id=%s",
            (context.workspace_id, extraction_id),
        )).fetchone()
        attachment = await (await connection.execute(
            "select * from public.attachments where workspace_id=%s and id=%s and state='validated' for update",
            (context.workspace_id, old["attachment_id"]),
        )).fetchone()
        if attachment is None:
            raise DomainError("NOT_FOUND", "Source attachment is unavailable", status=404)
        rows = await (await connection.execute(
            "select * from public.source_blocks where workspace_id=%s and attachment_id=%s and parser_version=%s order by ordinal",
            (context.workspace_id, old["attachment_id"], old["run_metadata"].get("parser_version", "v1")),
        )).fetchall()
        document = ParsedDocument(source_id=str(old["attachment_id"]), sha256=attachment["sha256"], format="txt", blocks=tuple(
            SourceBlock(id=str(r["id"]), source_id=str(old["attachment_id"]), text=r["text_content"],
                        locator=r["locator"], quality=float(r["quality"] if r["quality"] is not None else 0)) for r in rows
        ))
        original = Extraction.model_validate(old["output"])
        updated = original.model_copy(update={"fields": {**original.fields, body.field: body.value}})
        quality = ground_extraction(updated, document)
        if body.value.alternatives and any(v not in " ".join(e.quote for e in body.value.evidence) for v in body.value.alternatives):
            raise DomainError("PROVIDER_OUTPUT_INVALID", "Alternatives require supporting quotes")
        revision = (await (await connection.execute(
            "select coalesce(max(revision),0)+1 as n from public.document_extractions where workspace_id=%s and attachment_id=%s",
            (context.workspace_id, old["attachment_id"]),
        )).fetchone())["n"]
        new_id = uuid4()
        metadata = {**old["run_metadata"], "method": "human_review", "provider": "human", "quality": quality,
                    "reason": body.reason, "reviewer_id": str(context.user_id), "review_key": key,
                    "request_hash": request_hash, "parent_extraction_id": str(extraction_id)}
        metadata.pop("fallback_reason", None)
        await connection.execute(
            """insert into public.document_extractions(id,workspace_id,attachment_id,parent_id,revision,document_type,
            schema_version,cache_key,output,run_metadata,created_by) values(%s,%s,%s,%s,%s,%s,'v1',%s,%s,%s,%s)""",
            (new_id, context.workspace_id, old["attachment_id"], extraction_id, revision, old["document_type"],
             digest({"review_key": key, "request_hash": request_hash}), Jsonb(updated.model_dump(mode="json")), Jsonb(metadata), context.user_id),
        )
        await audit(connection, context, "extraction_reviewed", case_id,
                    {"parent_id": str(extraction_id), "extraction_id": str(new_id), "field": body.field, "reason": body.reason})
        return await select_sources_transaction(connection, case_id, SelectSources(
            expected_version=body.expected_version,
            si_extraction_id=new_id if case["active_si_id"] == extraction_id else case["active_si_id"],
            bl_extraction_id=new_id if case["active_bl_id"] == extraction_id else case["active_bl_id"],
            reason=body.reason,
        ), context, key)
