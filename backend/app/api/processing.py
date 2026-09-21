from fastapi import APIRouter, Request

from app.api.dependencies import Operator, Viewer
from app.repositories.emails import load_inbox
from app.services.offline_processing import queue_offline_processing

router = APIRouter(tags=["processing"])


@router.get("/workspace/processing")
async def processing_progress(request: Request, context: Viewer):
    """How far document reading and comparison has got, for a progress bar."""
    async with request.app.state.database.connection() as connection:
        items = await load_inbox(connection, context.workspace_id)
        ai = await (
            await connection.execute(
                """select
                (select count(*) from public.document_extractions where workspace_id=%s and run_metadata->>'method'='ai') as extractions,
                (select count(*) from public.email_classifications where workspace_id=%s and decided_by='ai') as classifications""",
                (context.workspace_id, context.workspace_id),
            )
        ).fetchone()
    eligible = [i for i in items if i["category"] == "BL_COMPARISON" and i["attachment_count"] > 0]
    unread = [i for i in eligible if i["documents"]["unread"] > 0]
    return {
        "eligible": len(eligible),
        "read": len(eligible) - len(unread),
        "compared": sum(1 for i in eligible if i["has_report"]),
        "failed": sum(1 for i in eligible if i["job_failed"]),
        # A job ran to the end but a file gave nothing: it could not be opened, and no more work is coming.
        "unreadable": sum(1 for i in unread if i["job_state"] == "succeeded"),
        # Not read, not running, not failed and not finished: waiting for a worker or for a release.
        "waiting": sum(
            1 for i in unread if i["state"] != "processing" and i["job_state"] not in ("failed", "succeeded")
        ),
        "active": any(i["state"] == "processing" for i in items),
        # Answers produced by an AI provider so far (the rules-only pipeline adds none).
        "ai_extractions": ai["extractions"],
        "ai_classifications": ai["classifications"],
    }


@router.post("/workspace/process")
async def process_documents(request: Request, context: Operator):
    """Queue rules-only reading and comparison of every unread comparison email."""
    async with request.app.state.database.connection() as connection:
        return await queue_offline_processing(connection, context.workspace_id)
