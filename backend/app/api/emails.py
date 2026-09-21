from uuid import UUID

from fastapi import APIRouter, Query, Request
from psycopg.types.json import Jsonb
from pydantic import Field

from app.api.dependencies import IdempotencyKey, Operator, Reviewer, Viewer
from app.domain.errors import DomainError
from app.domain.models import StrictModel
from app.repositories.emails import load_field_sources, load_inbox
from app.repositories.jobs import digest
from app.services.classification import segment_email
from app.services.email_extraction import extract_email_body
from app.services.email_preview import classification_summary, field_table
from app.services.email_state import ATTENTION_ORDER, STATES
from app.services.references import check_email
from app.services.safety_review import assess_stored
from app.services.workflow import start_workflow

router = APIRouter(tags=["emails"])


class CreateEmail(StrictModel):
    external_id: str = Field(min_length=1, max_length=240)
    sender: str = Field(alias="from", min_length=1, max_length=320)
    subject: str = Field(default="", max_length=1000)
    body: str = Field(min_length=1, max_length=100_000)
    source_namespace: str = Field(default="manual", min_length=1, max_length=80)


@router.post("/emails", status_code=201)
async def create_email(body: CreateEmail, request: Request, context: Operator):
    content_hash = digest(body.model_dump())
    async with request.app.state.database.connection() as connection:
        cursor = await connection.execute(
            """insert into public.emails(workspace_id,source_namespace,external_id,sender,subject,body,content_sha256,segments)
            values(%s,%s,%s,%s,%s,%s,%s,%s) on conflict(workspace_id,source_namespace,external_id) do nothing returning id,content_sha256""",
            (
                context.workspace_id,
                body.source_namespace,
                body.external_id,
                body.sender,
                body.subject,
                body.body,
                content_hash,
                Jsonb(segment_email(body.subject, body.body)),
            ),
        )
        email = await cursor.fetchone()
        if email is None:
            cursor = await connection.execute(
                "select id,content_sha256 from public.emails where workspace_id=%s and source_namespace=%s and external_id=%s",
                (context.workspace_id, body.source_namespace, body.external_id),
            )
            email = await cursor.fetchone()
            if email["content_sha256"] != content_hash:
                raise DomainError(
                    "IDEMPOTENCY_CONFLICT",
                    "Email identity already exists with different content",
                    status=409,
                )
        await assess_stored(connection, context.workspace_id, email["id"])
    return {"id": email["id"]}


def _matches(item, *, category, state, q, unresolved, safety, classified, verified, failed):
    needle = (q or "").strip().casefold()
    return (
        (category is None or item["category"] == category)
        and (state is None or item["state"] == state)
        and (
            not needle
            or any(
                needle in str(item[key] or "").casefold()
                for key in ("subject", "sender", "display_id", "external_id")
            )
        )
        and (not unresolved or item["category"] is None)
        and (not safety or item["state"] == "held")
        and (not classified or item["category"] is not None)
        and (not verified or item["has_report"])
        and (not failed or item["job_failed"])
    )


@router.get("/emails")
async def list_emails(
    request: Request,
    context: Viewer,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0, le=1_000_000),
    category: str | None = None,
    state: str | None = None,
    q: str | None = Query(None, max_length=200),
    unresolved: bool = False,
    safety: bool = False,
    classified: bool = False,
    verified: bool = False,
    failed: bool = False,
    trash: bool = False,
    attention: bool = False,
):
    """Emails with their derived review state, filtered and paged on the server.

    `attention` keeps only the states a person has to act on, most urgent first.
    """
    if state is not None and state not in STATES:
        raise DomainError("INVALID_STATE", f"Unknown review state: {state}", status=422)
    async with request.app.state.database.connection() as connection:
        everything = await load_inbox(connection, context.workspace_id, trash=trash)
    wanted = [
        item
        for item in everything
        if _matches(
            item, category=category, state=state, q=q, unresolved=unresolved, safety=safety,
            classified=classified, verified=verified, failed=failed,
        )
        and (not attention or item["state"] in ATTENTION_ORDER)
    ]
    if attention:  # stable sort: within a state the list keeps its own newest-first order
        wanted.sort(key=lambda item: ATTENTION_ORDER.index(item["state"]))
    return {
        "items": wanted[offset : offset + limit],
        "total": len(wanted),
        "next_cursor": str(offset + limit) if len(wanted) > offset + limit else None,
    }


@router.get("/emails/counts")
async def email_counts(request: Request, context: Viewer):
    """Totals by review state and by category, for the inbox filter badges."""
    async with request.app.state.database.connection() as connection:
        everything = await load_inbox(connection, context.workspace_id)
    by_state = dict.fromkeys(STATES, 0)
    by_category = dict.fromkeys(("BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM", "unclassified"), 0)
    for item in everything:
        by_state[item["state"]] += 1
        by_category[item["category"] or "unclassified"] += 1
    return {"total": len(everything), "by_state": by_state, "by_category": by_category}


@router.get("/emails/{email_id}")
async def get_email(email_id: UUID, request: Request, context: Viewer):
    async with request.app.state.database.connection() as connection:
        cursor = await connection.execute(
            "select id,external_id,sender,subject,body,segments from public.emails where workspace_id=%s and id=%s and deleted_at is null",
            (context.workspace_id, email_id),
        )
        email = await cursor.fetchone()
        if email is None:
            raise DomainError("NOT_FOUND", "Email was not found", status=404)
        segments = email.pop("segments") or []
        cursor = await connection.execute(
            "select id,original_name,mime_type,byte_size,state from public.attachments where workspace_id=%s and email_id=%s order by created_at",
            (context.workspace_id, email_id),
        )
        email["attachments"] = await cursor.fetchall()
        email["classification"] = await (
            await connection.execute(
                "select category,ambiguous,decided_by,evidence,run_metadata from public.email_classifications where workspace_id=%s and email_id=%s order by revision desc limit 1",
                (context.workspace_id, email_id),
            )
        ).fetchone()
        email["safety"] = await (
            await connection.execute(
                "select risk_state,severity,held_for_review,signals,release_reason from public.email_safety where workspace_id=%s and email_id=%s",
                (context.workspace_id, email_id),
            )
        ).fetchone()
        email["workflow"] = await (
            await connection.execute(
                """select w.*,j.state as job_state,j.error_code from public.email_workflows w
            left join public.processing_jobs j on j.workspace_id=w.workspace_id and j.id=w.job_id
            where w.workspace_id=%s and w.email_id=%s""",
                (context.workspace_id, email_id),
            )
        ).fetchone()
        email["extractions"] = await (
            await connection.execute(
                """select distinct on(x.attachment_id) x.id,x.attachment_id,x.document_type,x.output,x.run_metadata
            from public.document_extractions x join public.attachments a on a.workspace_id=x.workspace_id and a.id=x.attachment_id
            where x.workspace_id=%s and a.email_id=%s order by x.attachment_id,x.revision desc""",
                (context.workspace_id, email_id),
            )
        ).fetchall()
        email["body_extraction"] = extract_email_body(
            str(email_id), email["subject"], email["body"]
        )
        review = (await load_inbox(connection, context.workspace_id, email_id))[0]
        email.update({key: review[key] for key in (
            "display_id", "state", "state_label", "tone", "reasons", "action", "documents", "case",
        )})
        report, si_output, bl_output = await load_field_sources(
            connection, context.workspace_id, email_id, email["extractions"]
        )
        email["reference_check"] = await check_email(
            connection, context.workspace_id, email_id, email["subject"], email["body"], bool(email["attachments"])
        )
        email["classification_summary"] = classification_summary(email["classification"], segments)
        email["field_table"] = field_table(
            report, si_output, bl_output, email["body_extraction"]["extraction"]["fields"]
        )
        return email


class ProcessEmail(StrictModel):
    prefer_ai: bool = True


@router.post("/emails/{email_id}/process")
async def process_email(
    email_id: UUID, body: ProcessEmail, request: Request, context: Operator, key: IdempotencyKey
):
    async with request.app.state.database.connection() as connection:
        return await start_workflow(connection, context.workspace_id, email_id, key, body.prefer_ai)


class ReleaseEmail(StrictModel):
    reason: str = Field(min_length=5, max_length=1000)


@router.post("/emails/{email_id}/release")
async def release_email(email_id: UUID, body: ReleaseEmail, request: Request, context: Reviewer):
    async with request.app.state.database.connection() as connection:
        result = await connection.execute(
            """update public.email_safety set held_for_review=false,
            reviewed_by=%s,released_at=now(),release_reason=%s where workspace_id=%s and email_id=%s and held_for_review""",
            (context.user_id, body.reason, context.workspace_id, email_id),
        )
        if result.rowcount != 1:
            raise DomainError("NOT_HELD", "This email is not awaiting safety release", status=409)
    return {"state": "released"}
