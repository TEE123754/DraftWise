from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from app.domain.errors import DomainError
from app.domain.models import VerificationReport
from app.services.readiness import case_readiness
from app.services.revision_analysis import analyze_revision


async def get_case(connection, workspace_id, case_id, *, lock=False):
    cursor = await connection.execute(
        "select * from public.cases c where workspace_id=%s and id=%s and exists(select 1 from public.emails e where e.workspace_id=c.workspace_id and e.id=c.email_id and e.deleted_at is null)"
        + (" for update" if lock else ""),
        (workspace_id, case_id),
    )
    case = await cursor.fetchone()
    if case is None:
        raise DomainError("NOT_FOUND", "Case was not found", status=404)
    return case


def require_version(case, expected):
    if case["version"] != expected:
        raise DomainError("STALE_REVIEW", "This case changed. Reload before saving.", status=409)


async def audit(connection, context, action, case_id, details=None):
    await connection.execute(
        """insert into public.audit_logs(workspace_id,actor_id,actor_type,action,entity_type,entity_id,request_id,details)
        values(%s,%s,'user',%s,'case',%s,%s,%s)""",
        (context.workspace_id, context.user_id, action, case_id, uuid4(), Jsonb(details or {})),
    )


async def project_report(connection, job, report, si_id, bl_id):
    workspace, payload = job["workspace_id"], job["payload"]
    case = await get_case(connection, workspace, UUID(payload["case_id"]), lock=True)
    if case["latest_report_id"] == report.id:
        return
    if (
        case["version"] != payload["case_version"]
        or str(case["active_si_id"]) != str(si_id)
        or str(case["active_bl_id"]) != str(bl_id)
    ):
        return  # Keep historical output; never replace newer case state.
    previous = None
    if case["latest_report_id"]:
        cursor = await connection.execute(
            "select report from public.verification_reports where workspace_id=%s and id=%s",
            (workspace, case["latest_report_id"]),
        )
        row = await cursor.fetchone()
        previous = VerificationReport.model_validate(row["report"]) if row else None
        if previous and previous.comparisons[0].si.extraction_id != si_id:
            previous = None
    if si_id and bl_id and (previous is None or previous.comparisons[0].bl.extraction_id != bl_id):
        summary = analyze_revision(
            previous,
            report,
            case_id=case["id"],
            baseline_version=case["baseline_version"],
            policy_version=case["policy_version"],
            previous_policy_version=case["policy_version"] if previous else None,
        )
        await connection.execute(
            """insert into public.amendment_rounds(workspace_id,case_id,baseline_version,round_number,si_extraction_id,previous_bl_id,new_bl_id,previous_report_id,new_report_id,policy_version,summary)
            select %s,%s,%s,
              (select coalesce(max(round_number),0)+1 from public.amendment_rounds where workspace_id=%s and case_id=%s),
              %s,%s,%s,%s,%s,%s,%s on conflict(workspace_id,case_id,baseline_version,new_bl_id,policy_version) do nothing""",
            (
                workspace,
                case["id"],
                case["baseline_version"],
                workspace,
                case["id"],
                si_id,
                summary.previous_bl_id,
                bl_id,
                previous.id if previous else None,
                report.id,
                case["policy_version"],
                Jsonb(summary.model_dump(mode="json")),
            ),
        )
    # One statement for every field that now matches and one for every field that does not, rather
    # than one per field: each round trip to a hosted database costs ~100 ms.
    matched = [row.field.value for row in report.comparisons if row.decision == "match"]
    if matched:
        await connection.execute(
            """update public.case_issues set state='resolved',resolved_report_id=%s,updated_at=now()
            where workspace_id=%s and case_id=%s and baseline_version=%s and field::text=any(%s) and state='open'""",
            (report.id, workspace, case["id"], case["baseline_version"], matched),
        )
    open_issues = [
        {
            "field": row.field.value,
            "kind": "mismatch"
            if row.decision == "mismatch"
            else ("missing" if row.decision == "missing" else "ambiguous"),
            "evidence": list(row.evidence_ids),
        }
        for row in report.comparisons
        if row.decision != "match"
    ]
    if open_issues:
        await connection.execute(
            """insert into public.case_issues(workspace_id,case_id,baseline_version,field,kind,source_report_id,evidence)
            select %s,%s,%s,x.field::public.field_name,x.kind,%s,x.evidence
            from jsonb_to_recordset(%s) as x(field text,kind text,evidence jsonb)
            on conflict(workspace_id,case_id,baseline_version,field) where state='open'
            do update set source_report_id=excluded.source_report_id,evidence=excluded.evidence,kind=excluded.kind,updated_at=now()""",
            (workspace, case["id"], case["baseline_version"], report.id, Jsonb(open_issues)),
        )
    state = case_readiness(report, has_si=bool(si_id), has_bl=bool(bl_id))
    await connection.execute(
        """with updated as (
            update public.cases set latest_report_id=%s,readiness=%s,version=version+1,updated_at=now()
            where workspace_id=%s and id=%s returning id)
        update public.amendment_drafts set state='stale' where workspace_id=%s and case_id=%s and state='draft'""",
        (report.id, state, workspace, case["id"], workspace, case["id"]),
    )
