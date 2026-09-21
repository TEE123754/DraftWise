import uuid
from typing import Literal

from fastapi import APIRouter, Request
from psycopg.errors import UndefinedColumn, UndefinedTable
from pydantic import BaseModel, Field

from app.api.dependencies import Reviewer, Viewer
from app.domain.errors import DomainError
from app.api.email_actions import Reason
from app.services.email_actions import record_action,relabel_release,trash_email

router = APIRouter(tags=["alerts"])


class AcknowledgeRequest(BaseModel):
    assignee_note: str = Field(default="", max_length=500)


class ResolveRequest(Reason):
    pass


@router.get("/alerts")
async def list_alerts(request: Request, ctx: Viewer):
    """List all drift and safety alerts for the workspace."""
    workspace_id = ctx.workspace_id
    items = []

    try:
        async with request.app.state.database.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, alert_type, severity, title, description,
                       affected_window_start, affected_window_end,
                       sample_email_ids, lifecycle, created_at,baseline_version,changed_features,investigation_note,resolved_reason
                FROM public.drift_alerts
                WHERE workspace_id = %s
                ORDER BY
                    CASE lifecycle WHEN 'open' THEN 0 WHEN 'acknowledged' THEN 1 ELSE 2 END,
                    created_at DESC
                LIMIT 50
                """,
                (workspace_id,),
            )
            rows = await cursor.fetchall()
            for row in rows:
                items.append(
                    {
                        "id": str(row["id"]),
                        "alert_type": row["alert_type"],
                        "severity": row["severity"],
                        "title": row["title"],
                        "description": row["description"],
                        "affected_window_start": (
                            row["affected_window_start"].isoformat()
                            if row["affected_window_start"]
                            else None
                        ),
                        "affected_window_end": (
                            row["affected_window_end"].isoformat()
                            if row["affected_window_end"]
                            else None
                        ),
                        "sample_email_ids": row["sample_email_ids"] or [],
                        "lifecycle": row["lifecycle"],
                        "baseline_version": row["baseline_version"],
                        "changed_features": row["changed_features"],
                        "investigation_note": row["investigation_note"],
                        "resolved_reason": row["resolved_reason"],
                        "created_at": (
                            row["created_at"].isoformat() if row["created_at"] else None
                        ),
                    }
                )
    except (UndefinedTable, UndefinedColumn) as exc:
        raise DomainError(
            "ALERTS_UNAVAILABLE",
            "Alert monitoring is not configured. No detection result is available.",
            status=503,
        ) from exc

    return {"items": items}


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    request: Request,
    alert_id: uuid.UUID,
    ctx: Reviewer,
    body: AcknowledgeRequest = AcknowledgeRequest(),
):
    """Acknowledge an alert and optionally assign a reviewer note."""
    async with request.app.state.database.connection() as conn:
        result = await conn.execute(
            """
            UPDATE public.drift_alerts
            SET lifecycle='acknowledged', acknowledged_by=%s, acknowledged_at=NOW()
            WHERE id=%s AND workspace_id=%s AND lifecycle='open'
            """,
            (ctx.user_id, alert_id, ctx.workspace_id),
        )
        if result.rowcount != 1:
            raise DomainError(
                "ALERT_NOT_OPEN", "Alert was not found or is no longer open.", status=409
            )
    return {"state": "acknowledged"}


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(request: Request, alert_id: uuid.UUID, ctx: Reviewer, body: ResolveRequest):
    """Resolve or dismiss an alert with a mandatory reason."""
    async with request.app.state.database.connection() as conn:
        result = await conn.execute(
            """
            UPDATE public.drift_alerts
            SET lifecycle='resolved', resolved_by=%s, resolved_at=NOW(), resolved_reason=%s
            WHERE id=%s AND workspace_id=%s AND lifecycle IN ('open','acknowledged','investigated')
            """,
            (ctx.user_id, body.reason, alert_id, ctx.workspace_id),
        )
        if result.rowcount != 1:
            raise DomainError(
                "ALERT_NOT_OPEN", "Alert was not found or is no longer open.", status=409
            )
    return {"state": "resolved"}


class AlertAction(Reason):
    action: Literal["investigate","resolve","not_spam","confirm_spam"]
    category: Literal["BL_COMPARISON","SI_REQUEST","INVOICE_QUERY","GENERAL"] = "GENERAL"


@router.post("/alerts/{alert_id}/action")
async def act_on_alert(alert_id:uuid.UUID,body:AlertAction,request:Request,ctx:Reviewer):
    async with request.app.state.database.connection() as conn:
        alert=await (await conn.execute("select * from public.drift_alerts where workspace_id=%s and id=%s for update",(ctx.workspace_id,alert_id))).fetchone()
        if not alert: raise DomainError("NOT_FOUND","Alert was not found",status=404)
        if alert["lifecycle"] in {"resolved","dismissed"}: raise DomainError("ALERT_CLOSED","This alert is already closed",status=409)
        if body.action in {"not_spam","confirm_spam"}:
            if alert["alert_type"] not in {"spam","phishing"}: raise DomainError("INVALID_ACTION","Review drift samples individually",status=422)
            if not alert["sample_email_ids"]: raise DomainError("NO_SAMPLES","This alert has no source email",status=409)
            for email_id in sorted(uuid.UUID(x) for x in alert["sample_email_ids"]):
                await relabel_release(conn,ctx,email_id,"SPAM" if body.action=="confirm_spam" else body.category,body.reason)
                if body.action=="confirm_spam": await trash_email(conn,ctx,email_id,body.reason)
        state="investigated" if body.action=="investigate" else "resolved"
        await conn.execute("""update public.drift_alerts set lifecycle=%s,investigation_note=%s,updated_at=now(),
            resolved_reason=case when %s='resolved' then %s else resolved_reason end,
            resolved_by=case when %s='resolved' then %s else resolved_by end,
            resolved_at=case when %s='resolved' then now() else resolved_at end where workspace_id=%s and id=%s""",
            (state,body.reason,state,body.reason,state,ctx.user_id,state,ctx.workspace_id,alert_id))
        await record_action(conn,ctx,"alert_"+body.action,alert_id,{"reason":body.reason,"sample_count":len(alert["sample_email_ids"])})
    return {"state":state}
