import hashlib
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Query, Request
from psycopg.types.json import Jsonb
from pydantic import Field

from app.api.dependencies import IdempotencyKey, Reviewer, Viewer
from app.domain.errors import DomainError
from app.domain.models import PARTIES, PORTS, FieldName, StrictModel
from app.repositories.cases import audit, get_case
from app.repositories.jobs import enqueue
from app.services.equivalence_rules import EquivalenceRule

router = APIRouter(tags=["rules"])


class CreateRule(StrictModel):
    field: FieldName
    left_value: str = Field(min_length=1, max_length=4000)
    right_value: str = Field(min_length=1, max_length=4000)
    evidence_ids: list[str] = Field(default_factory=list)
    rationale: str = Field(min_length=5, max_length=1000)
    auto_approve: bool = True


class RevokeRule(StrictModel):
    rationale: str = Field(min_length=5, max_length=1000)


@router.get("/rules")
async def list_workspace_rules(
    request: Request,
    context: Viewer,
    customer_id: UUID | None = None,
    field: FieldName | None = None,
    state: Literal["proposed", "approved", "revoked"] | None = None,
    limit: int = Query(50, ge=1, le=100),
):
    async with request.app.state.database.connection() as connection:
        cursor = await connection.execute(
            """select id, workspace_id, customer_id, field, left_value, right_value,
                      version, state, content_sha256, evidence, proposed_by, approved_by,
                      approved_at, created_at
            from public.equivalence_rules
            where workspace_id=%s
              and (%s::uuid is null or customer_id=%s)
              and (%s::text is null or field=%s)
              and (%s::text is null or state=%s)
            order by created_at desc limit %s""",
            (
                context.workspace_id,
                customer_id,
                customer_id,
                field.value if field else None,
                field.value if field else None,
                state,
                state,
                limit,
            ),
        )
        rows = await cursor.fetchall()
    return {"items": rows}


@router.get("/cases/{case_id}/rules")
async def list_case_rules(case_id: UUID, request: Request, context: Viewer):
    async with request.app.state.database.connection() as connection:
        case = await get_case(connection, context.workspace_id, case_id)
        if not case.get("customer_id"):
            return {"items": []}
        cursor = await connection.execute(
            """select id, workspace_id, customer_id, field, left_value, right_value,
                      version, state, content_sha256, evidence, proposed_by, approved_by,
                      approved_at, created_at
            from public.equivalence_rules
            where workspace_id=%s and customer_id=%s
            order by created_at desc limit 50""",
            (context.workspace_id, case["customer_id"]),
        )
        rows = await cursor.fetchall()
    return {"items": rows}


@router.post("/cases/{case_id}/rules", status_code=201)
async def create_case_rule(
    case_id: UUID,
    body: CreateRule,
    request: Request,
    context: Reviewer,
    key: IdempotencyKey,
):
    if body.field not in PARTIES | PORTS:
        raise DomainError(
            "RULE_FIELD_UNSUPPORTED",
            "Equivalence rules are only allowed for parties and ports",
            status=422,
        )
    if body.left_value.strip() == body.right_value.strip():
        raise DomainError("RULE_VALUE_INVALID", "Left and right identities must be different", status=422)

    # Validate using domain model
    rule_id = uuid4()
    domain_rule = EquivalenceRule(
        id=rule_id,
        workspace_id=context.workspace_id,
        customer_id=uuid4(),  # placeholder, overridden with case customer_id
        field=body.field,
        left=body.left_value,
        right=body.right_value,
        evidence_ids=tuple(body.evidence_ids or ["manual_review"]),
        rationale=body.rationale,
        canonical_port_code="UNLOC" if body.field in PORTS else None,
        authority_reference="manual_review" if body.field in PORTS else None,
    )

    async with request.app.state.database.connection() as connection:
        case = await get_case(connection, context.workspace_id, case_id, lock=True)
        customer_id = case.get("customer_id")
        if not customer_id:
            # Look up or create a customer record for this workspace
            cursor = await connection.execute(
                "select id from public.customers where workspace_id=%s limit 1",
                (context.workspace_id,),
            )
            cust_row = await cursor.fetchone()
            if cust_row:
                customer_id = cust_row["id"]
            else:
                customer_id = uuid4()
                await connection.execute(
                    """insert into public.customers(id, workspace_id, name)
                    values(%s, %s, 'Default Customer') on conflict do nothing""",
                    (customer_id, context.workspace_id),
                )
            await connection.execute(
                "update public.cases set customer_id=%s where workspace_id=%s and id=%s",
                (customer_id, context.workspace_id, case_id),
            )

        content_sha256 = hashlib.sha256(
            f"{context.workspace_id}:{customer_id}:{body.field.value}:{body.left_value}:{body.right_value}".encode()
        ).hexdigest()

        state = "approved" if body.auto_approve else "proposed"
        approved_by = context.user_id if body.auto_approve else None

        await connection.execute(
            """insert into public.equivalence_rules(
                id, workspace_id, customer_id, field, left_value, right_value,
                version, state, content_sha256, evidence, proposed_by,
                approved_by, approved_at
            ) values(%s, %s, %s, %s, %s, %s, 1, %s, %s, %s, %s, %s, case when %s='approved' then now() else null end)
            on conflict (workspace_id, id) do nothing""",
            (
                rule_id,
                context.workspace_id,
                customer_id,
                body.field.value,
                body.left_value,
                body.right_value,
                state,
                content_sha256,
                Jsonb(list(domain_rule.evidence_ids)),
                context.user_id,
                approved_by,
                state,
            ),
        )

        await audit(
            connection,
            context,
            "equivalence_rule_created",
            case_id,
            {
                "rule_id": str(rule_id),
                "field": body.field.value,
                "left": body.left_value,
                "right": body.right_value,
                "state": state,
                "rationale": body.rationale,
            },
        )

        # Trigger re-verification job for the case so the new rule takes effect
        job = None
        if case["active_si_id"] and case["active_bl_id"]:
            version = case["version"] + 1
            await connection.execute(
                "update public.cases set version=%s, readiness='checking', updated_at=now() where workspace_id=%s and id=%s",
                (version, context.workspace_id, case_id),
            )
            payload = {
                "operation": "compare",
                "email_id": str(case["email_id"]),
                "case_id": str(case_id),
                "case_version": version,
                "si_extraction_id": str(case["active_si_id"]),
                "bl_extraction_id": str(case["active_bl_id"]),
                "policy_version": case.get("policy_version", "v1"),
                "customer_id": str(customer_id),
            }
            job = await enqueue(
                connection,
                workspace_id=context.workspace_id,
                kind="verify",
                key=key,
                payload=payload,
                email_id=case["email_id"],
            )

    return {
        "rule_id": str(rule_id),
        "state": state,
        "job_id": job["id"] if job else None,
    }


@router.post("/rules/{rule_id}/approve")
async def approve_equivalence_rule(rule_id: UUID, request: Request, context: Reviewer):
    async with request.app.state.database.connection() as connection:
        cursor = await connection.execute(
            "select * from public.equivalence_rules where workspace_id=%s and id=%s for update",
            (context.workspace_id, rule_id),
        )
        rule = await cursor.fetchone()
        if not rule:
            raise DomainError("NOT_FOUND", "Equivalence rule not found", status=404)
        if rule["state"] == "approved":
            return {"rule_id": str(rule_id), "state": "approved"}
        if rule["state"] == "revoked":
            raise DomainError("RULE_STATE_INVALID", "Cannot approve a revoked rule", status=409)

        await connection.execute(
            """update public.equivalence_rules
            set state='approved', approved_by=%s, approved_at=now()
            where workspace_id=%s and id=%s""",
            (context.user_id, context.workspace_id, rule_id),
        )
    return {"rule_id": str(rule_id), "state": "approved"}


@router.post("/rules/{rule_id}/revoke")
async def revoke_equivalence_rule(
    rule_id: UUID,
    body: RevokeRule,
    request: Request,
    context: Reviewer,
):
    async with request.app.state.database.connection() as connection:
        cursor = await connection.execute(
            "select * from public.equivalence_rules where workspace_id=%s and id=%s for update",
            (context.workspace_id, rule_id),
        )
        rule = await cursor.fetchone()
        if not rule:
            raise DomainError("NOT_FOUND", "Equivalence rule not found", status=404)

        await connection.execute(
            """update public.equivalence_rules
            set state='revoked', version=version+1
            where workspace_id=%s and id=%s""",
            (context.workspace_id, rule_id),
        )

        # Find reports that applied this rule and mark them stale
        applied_cursor = await connection.execute(
            "select distinct report_id from public.report_rule_applications where workspace_id=%s and rule_id=%s",
            (context.workspace_id, rule_id),
        )
        stale_reports = [row["report_id"] for row in await applied_cursor.fetchall()]

        # Re-trigger verification for affected cases
        if stale_reports:
            case_cursor = await connection.execute(
                "select id, email_id, active_si_id, active_bl_id, version, policy_version, customer_id from public.cases where workspace_id=%s and latest_report_id=any(%s)",
                (context.workspace_id, stale_reports),
            )
            for c in await case_cursor.fetchall():
                if c["active_si_id"] and c["active_bl_id"]:
                    v = c["version"] + 1
                    await connection.execute(
                        "update public.cases set version=%s, readiness='checking', updated_at=now() where workspace_id=%s and id=%s",
                        (v, context.workspace_id, c["id"]),
                    )
                    await enqueue(
                        connection,
                        workspace_id=context.workspace_id,
                        kind="verify",
                        key=f"revoke:{rule_id}:{c['id']}",
                        payload={
                            "operation": "compare",
                            "email_id": str(c["email_id"]),
                            "case_id": str(c["id"]),
                            "case_version": v,
                            "si_extraction_id": str(c["active_si_id"]),
                            "bl_extraction_id": str(c["active_bl_id"]),
                            "policy_version": c.get("policy_version", "v1"),
                            "customer_id": str(c.get("customer_id") or ""),
                        },
                        email_id=c["email_id"],
                    )

    return {"rule_id": str(rule_id), "state": "revoked", "stale_reports_count": len(stale_reports)}
