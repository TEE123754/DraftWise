from uuid import UUID

from fastapi import APIRouter, Request
from psycopg.types.json import Jsonb
from pydantic import Field

from app.api.dependencies import IdempotencyKey, Operator, Reviewer
from app.domain.errors import DomainError
from app.domain.models import StrictModel, VerificationReport
from app.repositories.cases import audit, get_case, require_version
from app.repositories.jobs import enqueue
from app.services.amendment_drafts import draft_request
from app.services.correction_previews import CorrectionPreview, create_preview, validate_preview

router = APIRouter(tags=["amendments"])


class DraftIntake(StrictModel):
    expected_version: int = Field(ge=1)
    attachment_id: UUID


@router.post("/cases/{case_id}/drafts", status_code=202)
async def draft_intake(
    case_id: UUID, body: DraftIntake, request: Request, context: Operator, key: IdempotencyKey
):
    async with request.app.state.database.connection() as connection:
        case = await get_case(connection, context.workspace_id, case_id, lock=True)
        require_version(case, body.expected_version)
        cursor = await connection.execute(
            "select id from public.attachments where workspace_id=%s and id=%s and email_id=%s and state='validated'",
            (context.workspace_id, body.attachment_id, case["email_id"]),
        )
        if await cursor.fetchone() is None:
            raise DomainError("NOT_FOUND", "Finalized case attachment was not found", status=404)
        # Extract first. A reviewer confirms the returned source before it becomes active.
        job = await enqueue(
            connection,
            workspace_id=context.workspace_id,
            kind="extract",
            key=key,
            payload={
                "attachment_ids": [str(body.attachment_id)],
                "role_hints": {str(body.attachment_id): "BL"},
                "reprocess": False,
            },
            email_id=case["email_id"],
        )
        await audit(
            connection,
            context,
            "returned_draft_added",
            case_id,
            {"attachment_id": str(body.attachment_id)},
        )
    return {"job_id": job["id"], "case_id": case_id, "case_version": case["version"]}


class PreviewRequest(StrictModel):
    expected_version: int = Field(ge=1)
    report_id: UUID
    issue_ids: tuple[UUID, ...] = Field(min_length=1, max_length=7)


async def current_report(connection, workspace_id, case):
    cursor = await connection.execute(
        "select report from public.verification_reports where workspace_id=%s and id=%s",
        (workspace_id, case["latest_report_id"]),
    )
    row = await cursor.fetchone()
    if row is None:
        raise DomainError("REPORT_REQUIRED", "Wait for the current document check", status=409)
    report = VerificationReport.model_validate(row["report"])
    if any(
        row.si.extraction_id != str(case["active_si_id"])
        or row.bl.extraction_id != str(case["active_bl_id"])
        for row in report.comparisons
    ):
        raise DomainError(
            "STALE_REPORT", "Wait for the selected sources to finish verification", status=409
        )
    return report


@router.post("/cases/{case_id}/previews", status_code=201)
async def preview(case_id: UUID, body: PreviewRequest, request: Request, context: Reviewer):
    async with request.app.state.database.connection() as connection:
        case = await get_case(connection, context.workspace_id, case_id, lock=True)
        require_version(case, body.expected_version)
        if case["latest_report_id"] != body.report_id:
            raise DomainError(
                "STALE_REPORT", "The selected report is no longer current", status=409
            )
        cursor = await connection.execute(
            "select field from public.case_issues where workspace_id=%s and case_id=%s and source_report_id=%s and state='open' and id=any(%s)",
            (context.workspace_id, case_id, body.report_id, list(body.issue_ids)),
        )
        issues = await cursor.fetchall()
        if len(issues) != len(body.issue_ids):
            raise DomainError("INVALID_ISSUE", "Select distinct current issues in this case")
        report = await current_report(connection, context.workspace_id, case)
        clock = await connection.execute("select now() as created_at")
        created_at = (await clock.fetchone())["created_at"]
        result = create_preview(
            report,
            workspace_id=context.workspace_id,
            case_id=case_id,
            case_version=case["version"],
            policy_version=case["policy_version"],
            fields=tuple(row["field"] for row in issues),
            now=created_at,
        )
        await connection.execute(
            """insert into public.correction_previews(id,workspace_id,case_id,case_version,report_id,fingerprint,payload,created_by,expires_at)
            values(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                result.id,
                context.workspace_id,
                case_id,
                case["version"],
                report.id,
                result.fingerprint,
                Jsonb(result.model_dump(mode="json")),
                context.user_id,
                result.expires_at,
            ),
        )
    return {
        **result.model_dump(mode="json"),
        "suggested_message": draft_request(case["reference"], result),
    }


class SaveRequest(StrictModel):
    expected_version: int = Field(ge=1)
    preview_id: UUID
    message: str = Field(min_length=1, max_length=8000)


@router.post("/cases/{case_id}/requests", status_code=201)
async def save_request(case_id: UUID, body: SaveRequest, request: Request, context: Reviewer):
    async with request.app.state.database.connection() as connection:
        case = await get_case(connection, context.workspace_id, case_id, lock=True)
        require_version(case, body.expected_version)
        cursor = await connection.execute(
            "select payload from public.correction_previews where workspace_id=%s and case_id=%s and id=%s",
            (context.workspace_id, case_id, body.preview_id),
        )
        row = await cursor.fetchone()
        if row is None:
            raise DomainError("NOT_FOUND", "Preview was not found", status=404)
        preview = CorrectionPreview.model_validate(row["payload"])
        report = await current_report(connection, context.workspace_id, case)
        validate_preview(
            preview,
            report,
            workspace_id=context.workspace_id,
            case_id=case_id,
            case_version=case["version"],
            policy_version=case["policy_version"],
        )
        if body.message != draft_request(case["reference"], preview):
            raise DomainError(
                "REQUEST_TEXT_UNSUPPORTED",
                "Use the source-supported generated request; custom wording is not enabled yet",
            )
        changes = [patch.model_dump(mode="json") for patch in preview.changes]
        cursor = await connection.execute(
            """insert into public.amendment_drafts(workspace_id,case_id,preview_id,case_version,message,requested_changes,created_by)
            values(%s,%s,%s,%s,%s,%s,%s) returning id""",
            (
                context.workspace_id,
                case_id,
                preview.id,
                case["version"],
                body.message,
                Jsonb(changes),
                context.user_id,
            ),
        )
        request_id = (await cursor.fetchone())["id"]
        await audit(connection, context, "request_saved", case_id, {"request_id": str(request_id)})
    return {
        "id": request_id,
        "state": "draft",
        "case_version": case["version"],
        "requested_changes": changes,
        "message": body.message,
    }


class SharedRequest(StrictModel):
    expected_version: int = Field(ge=1)
    note: str = Field(min_length=1, max_length=1000)


@router.post("/cases/{case_id}/requests/{request_id}/shared")
async def mark_shared(
    case_id: UUID, request_id: UUID, body: SharedRequest, request: Request, context: Reviewer
):
    async with request.app.state.database.connection() as connection:
        case = await get_case(connection, context.workspace_id, case_id, lock=True)
        require_version(case, body.expected_version)
        cursor = await connection.execute(
            """select d.*,p.payload as preview_payload from public.amendment_drafts d join public.correction_previews p
            on p.workspace_id=d.workspace_id and p.id=d.preview_id where d.workspace_id=%s and d.case_id=%s and d.id=%s for update of d""",
            (context.workspace_id, case_id, request_id),
        )
        draft = await cursor.fetchone()
        if draft is None:
            raise DomainError("NOT_FOUND", "Request was not found", status=404)
        if draft["state"] != "draft" or draft["case_version"] != case["version"]:
            raise DomainError("STALE_REQUEST", "This request is no longer current", status=409)
        validate_preview(
            CorrectionPreview.model_validate(draft["preview_payload"]),
            await current_report(connection, context.workspace_id, case),
            workspace_id=context.workspace_id,
            case_id=case_id,
            case_version=case["version"],
            policy_version=case["policy_version"],
        )
        await connection.execute(
            "update public.amendment_drafts set state='marked_shared',shared_note=%s,shared_at=now() where workspace_id=%s and id=%s",
            (body.note, context.workspace_id, request_id),
        )
        await connection.execute(
            "update public.cases set readiness='awaiting_revision',version=version+1,updated_at=now() where workspace_id=%s and id=%s",
            (context.workspace_id, case_id),
        )
        await audit(
            connection,
            context,
            "request_marked_shared",
            case_id,
            {"request_id": str(request_id), "note": body.note},
        )
    return {
        "request_id": request_id,
        "state": "marked_shared",
        "case_version": case["version"] + 1,
        "readiness": "awaiting_revision",
    }
