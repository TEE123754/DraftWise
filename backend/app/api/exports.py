from uuid import UUID

from fastapi import APIRouter, Request, Response

from app.api.dependencies import Viewer
from app.domain.errors import DomainError
from app.services.report_export import report_rows, to_csv

router = APIRouter(tags=["exports"])

LATEST_REPORTS_SQL = """
select distinct on (r.email_id) r.email_id, r.report, e.external_id, e.subject, e.created_at
from public.verification_reports r
join public.emails e on e.workspace_id = r.workspace_id and e.id = r.email_id
where r.workspace_id = %s and e.deleted_at is null and (%s::uuid is null or e.id = %s::uuid)
order by r.email_id, r.revision desc
"""


@router.get("/exports/discrepancies.csv")
async def export_discrepancies(
    request: Request,
    context: Viewer,
    email_id: UUID | None = None,
    include_matches: bool = False,
):
    """The latest report of every email (or of one), as a CSV a reviewer can open in Excel."""
    async with request.app.state.database.connection() as connection:
        reports = await (
            await connection.execute(LATEST_REPORTS_SQL, (context.workspace_id, email_id, email_id))
        ).fetchall()
        if email_id and not reports:
            raise DomainError("NOT_FOUND", "This email has no verification report yet", status=404)
        wanted = {
            side["extraction_id"]
            for row in reports
            for comparison in row["report"]["comparisons"]
            for side in (comparison["si"], comparison["bl"])
            if side["extraction_id"]
        }
        extractions = (
            await (
                await connection.execute(
                    "select id::text as id, output from public.document_extractions"
                    " where workspace_id = %s and id::text = any(%s)",
                    (context.workspace_id, list(wanted)),
                )
            ).fetchall()
            if wanted
            else []
        )
    outputs = {row["id"]: row["output"] for row in extractions}
    rows = []
    for item in sorted(reports, key=lambda row: (row["created_at"], row["external_id"])):
        rows += report_rows(item, item["report"], outputs, include_matches=include_matches)
    scope = "email" if email_id else "workspace"
    return Response(
        content=to_csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="draftwise-discrepancies-{scope}.csv"',
            "Cache-Control": "no-store",
        },
    )
