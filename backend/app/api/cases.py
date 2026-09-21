import base64
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Query, Request, Response
from pydantic import Field

from app.api.dependencies import IdempotencyKey, Operator, Reviewer, Viewer
from app.api.document_actions import document_actions
from app.domain.errors import DomainError
from app.domain.models import StrictModel, VerificationReport
from app.repositories.cases import audit, get_case, require_version
from app.repositories.emails import load_inbox
from app.repositories.jobs import enqueue
from app.services.action_planner import next_action

router = APIRouter(tags=["cases"])
Readiness = Literal[
    "needs_source",
    "checking",
    "needs_decision",
    "changes_required",
    "awaiting_revision",
    "checked",
    "failed",
]


def offset_from_cursor(cursor: str | None) -> int:
    try:
        offset = int(base64.urlsafe_b64decode(cursor.encode()).decode()) if cursor else 0
        if not 0 <= offset <= 1_000_000:
            raise ValueError()
        return offset
    except (ValueError, UnicodeError) as exc:
        raise DomainError("VALIDATION_ERROR", "Invalid page cursor") from exc


@router.get("/cases")
async def list_cases(
    request: Request,
    context: Viewer,
    readiness: list[Readiness] | None = Query(None),
    open: bool = False,
    search: str = Query("", max_length=120),
    limit: int = Query(25, ge=1, le=100),
    cursor: str | None = None,
):
    offset = offset_from_cursor(cursor)
    async with request.app.state.database.connection() as connection:
        result = await connection.execute(
            """select c.*,r.report,
            (select count(*) from public.case_issues i where i.workspace_id=c.workspace_id and i.case_id=c.id and i.state='open') as open_issue_count
            from public.cases c left join public.verification_reports r on r.workspace_id=c.workspace_id and r.id=c.latest_report_id
            where c.workspace_id=%s and exists(select 1 from public.emails e where e.workspace_id=c.workspace_id and e.id=c.email_id and e.deleted_at is null) and (%s::text[] is null or c.readiness=any(%s))
            and (not %s or c.readiness not in ('checked','failed')) and c.reference ilike %s
            order by case c.readiness when 'needs_decision' then 0 when 'changes_required' then 1 when 'failed' then 2
                when 'needs_source' then 3 when 'checking' then 4 when 'awaiting_revision' then 5 else 6 end,c.updated_at desc,c.id
            limit %s offset %s""",
            (context.workspace_id, readiness, readiness, open, f"%{search}%", limit + 1, offset),
        )
        items = await result.fetchall()
    more = len(items) > limit
    for item in items[:limit]:
        report = item.pop("report")
        item["next_action"] = next_action(
            VerificationReport.model_validate(report) if report else None,
            processing=item["readiness"] == "checking",
            failed=item["readiness"] == "failed",
            needs_source=item["readiness"] == "needs_source",
            awaiting_revision=item["readiness"] == "awaiting_revision",
        ).model_dump(mode="json")
    return {
        "items": items[:limit],
        "next_cursor": base64.urlsafe_b64encode(str(offset + limit).encode()).decode()
        if more
        else None,
    }


class CreateCase(StrictModel):
    email_id: UUID
    reference: str = Field(min_length=1, max_length=120)


@router.post("/cases", status_code=201)
async def create_case(body: CreateCase, request: Request, context: Operator, key: IdempotencyKey):
    async with request.app.state.database.connection() as connection:
        cursor = await connection.execute(
            "select id from public.emails where workspace_id=%s and id=%s for update",
            (context.workspace_id, body.email_id),
        )
        if await cursor.fetchone() is None:
            raise DomainError("NOT_FOUND", "Email was not found", status=404)
        cursor = await connection.execute(
            "select id,version,reference from public.cases where workspace_id=%s and email_id=%s",
            (context.workspace_id, body.email_id),
        )
        existing = await cursor.fetchone()
        if existing:
            if existing["reference"] != body.reference:
                raise DomainError(
                    "CASE_EXISTS",
                    "This email already belongs to a different case reference",
                    status=409,
                )
            return {"id": existing["id"], "version": existing["version"]}
        case_id = uuid4()
        await connection.execute(
            "insert into public.cases(id,workspace_id,email_id,reference) values(%s,%s,%s,%s)",
            (case_id, context.workspace_id, body.email_id, body.reference),
        )
        await audit(connection, context, "case_created", case_id, {"idempotency_key": key})
    return {"id": case_id, "version": 1}


@router.get("/cases/{case_id}")
async def case_detail(case_id: UUID, request: Request, response: Response, context: Viewer):
    async with request.app.state.database.connection() as connection:
        case = await get_case(connection, context.workspace_id, case_id)
        cursor = await connection.execute(
            "select report from public.verification_reports where workspace_id=%s and id=%s",
            (context.workspace_id, case["latest_report_id"]),
        )
        row = await cursor.fetchone()
        report = VerificationReport.model_validate(row["report"]) if row else None
        cursor = await connection.execute(
            "select id,field,state,kind,source_report_id,evidence from public.case_issues where workspace_id=%s and case_id=%s order by created_at",
            (context.workspace_id, case_id),
        )
        issues = await cursor.fetchall()
        cursor = await connection.execute(
            "select id,round_number,summary,created_at from public.amendment_rounds where workspace_id=%s and case_id=%s order by round_number desc",
            (context.workspace_id, case_id),
        )
        rounds = await cursor.fetchall()
        cursor = await connection.execute(
            """select x.id,x.attachment_id,x.document_type,x.revision,a.original_name from public.document_extractions x
            join public.attachments a on a.workspace_id=x.workspace_id and a.id=x.attachment_id where x.workspace_id=%s and a.email_id=%s order by x.created_at desc""",
            (context.workspace_id, case["email_id"]),
        )
        sources = await cursor.fetchall()
        cursor = await connection.execute(
            """select id,state,error_code,attempt from public.processing_jobs
            where workspace_id=%s and kind='verify' and payload->>'case_id'=%s
            and payload->>'case_version'=%s order by created_at desc limit 1""",
            (context.workspace_id, str(case_id), str(case["version"])),
        )
        current_job = await cursor.fetchone()
        inbox = await load_inbox(connection, context.workspace_id, case["email_id"])
        documents = document_actions(inbox[0]) if inbox else None
    case["open_issue_count"] = sum(item["state"] == "open" for item in issues)
    case["next_action"] = next_action(
        report,
        processing=case["readiness"] == "checking",
        failed=case["readiness"] == "failed",
        needs_source=case["readiness"] == "needs_source",
        awaiting_revision=case["readiness"] == "awaiting_revision",
    ).model_dump(mode="json")
    if documents and inbox[0]["state"] in {"needs_documents", "waiting_for_draft"}:
        case["next_action"] = {"kind": documents["kind"], "title": documents["title"], "fields": []}
    response.headers["ETag"] = f'"case-{case["version"]}"'
    return {
        "document_actions": documents,
        "case": case,
        "active_sources": {
            "si_extraction_id": case["active_si_id"],
            "bl_extraction_id": case["active_bl_id"],
        },
        "issues": issues,
        "actions": [],
        "rounds": rounds,
        "latest_report": report,
        "available_sources": sources,
        "current_job": current_job,
    }


class SelectSources(StrictModel):
    expected_version: int = Field(ge=1)
    si_extraction_id: UUID
    bl_extraction_id: UUID | None = None
    reason: str = Field(min_length=1, max_length=1000)


@router.post("/cases/{case_id}/sources", status_code=202)
async def select_sources(
    case_id: UUID, body: SelectSources, request: Request, context: Reviewer, key: IdempotencyKey
):
    async with request.app.state.database.connection() as connection:
        return await select_sources_transaction(connection, case_id, body, context, key)


async def select_sources_transaction(connection, case_id, body, context, key):
    case = await get_case(connection, context.workspace_id, case_id, lock=True)
    require_version(case, body.expected_version)
    for source_id, role in ((body.si_extraction_id, "SI"), (body.bl_extraction_id, "BL")):
        if source_id is None:
            continue
        cursor = await connection.execute(
            """select x.document_type from public.document_extractions x join public.attachments a
            on a.workspace_id=x.workspace_id and a.id=x.attachment_id where x.workspace_id=%s and x.id=%s and a.email_id=%s and a.state='validated'""",
            (context.workspace_id, source_id, case["email_id"]),
        )
        source = await cursor.fetchone()
        if source is None:
            raise DomainError("NOT_FOUND", "Source was not found for this case", status=404)
        if source["document_type"] != role:
            raise DomainError(
                "DOCUMENT_ROLE_INVALID", "Source content does not support the selected role"
            )
    rebaseline = (
        case["active_si_id"] is not None and case["active_si_id"] != body.si_extraction_id
    )
    changed = (
        case["active_si_id"] != body.si_extraction_id
        or case["active_bl_id"] != body.bl_extraction_id
    )
    version = case["version"] + int(changed)
    if changed:
        await connection.execute(
            """update public.cases set active_si_id=%s,active_bl_id=%s,version=%s,
            baseline_version=baseline_version+%s,readiness=%s,updated_at=now() where workspace_id=%s and id=%s""",
            (
                body.si_extraction_id,
                body.bl_extraction_id,
                version,
                int(rebaseline),
                "checking" if body.bl_extraction_id else "needs_source",
                context.workspace_id,
                case_id,
            ),
        )
        await connection.execute(
            "update public.amendment_drafts set state='stale' where workspace_id=%s and case_id=%s",
            (context.workspace_id, case_id),
        )
        await connection.execute(
            "update public.case_actions set state='stale' where workspace_id=%s and case_id=%s and state='open'",
            (context.workspace_id, case_id),
        )
        if rebaseline:
            await connection.execute(
                "update public.case_issues set state='superseded',updated_at=now() where workspace_id=%s and case_id=%s and state='open'",
                (context.workspace_id, case_id),
            )
        await audit(
            connection, context, "sources_selected", case_id, body.model_dump(mode="json")
        )
    payload = {
        "operation": "compare",
        "email_id": str(case["email_id"]),
        "case_id": str(case_id),
        "case_version": version,
        "si_extraction_id": str(body.si_extraction_id),
        "bl_extraction_id": str(body.bl_extraction_id) if body.bl_extraction_id else None,
        "policy_version": case["policy_version"],
    }
    job = await enqueue(
        connection,
        workspace_id=context.workspace_id,
        kind="verify",
        key=key,
        payload=payload,
        email_id=case["email_id"],
    )
    return {"job_id": job["id"], "case_id": case_id, "case_version": version}
