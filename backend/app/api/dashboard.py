from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Request
from psycopg.types.json import Jsonb
from pydantic import Field, model_validator

from app.api.dependencies import Viewer
from app.domain.models import StrictModel

router = APIRouter(tags=["dashboard"])


async def workspace_summary(connection, workspace_id):
    emails = await (
        await connection.execute(
            """select count(*) as total,count(*) filter(where c.category is not null and not c.ambiguous) as classified,
            count(*) filter(where c.category='SPAM' and not c.ambiguous) as spam
            from public.emails e left join lateral(select category,ambiguous from public.email_classifications
            where workspace_id=e.workspace_id and email_id=e.id order by revision desc limit 1)c on true where e.workspace_id=%s and e.deleted_at is null""",
            (workspace_id,),
        )
    ).fetchone()
    cases = await (
        await connection.execute(
            """select count(*) filter(where readiness not in ('checked','failed')) as open,
        count(*) filter(where readiness='checked') as checked,
        count(*) filter(where readiness='failed') as failed,
        count(*) filter(where readiness in ('needs_decision','changes_required')) as review,
        count(*) filter(where readiness='changes_required') as mismatches,
        count(*) filter(where readiness='awaiting_revision') as waiting
        from public.cases c where workspace_id=%s and exists(select 1 from public.emails e where e.id=c.email_id and e.workspace_id=c.workspace_id and e.deleted_at is null)""",
            (workspace_id,),
        )
    ).fetchone()
    jobs = await (
        await connection.execute(
            """select count(*) as active from public.processing_jobs where workspace_id=%s
        and state in ('queued','running','retry_wait')""",
            (workspace_id,),
        )
    ).fetchone()
    safety = await (
        await connection.execute(
            "select count(*) as assessed,count(*) filter(where held_for_review) as held from public.email_safety s where workspace_id=%s and exists(select 1 from public.emails e where e.id=s.email_id and e.workspace_id=s.workspace_id and e.deleted_at is null)",
            (workspace_id,),
        )
    ).fetchone()
    drift = await (
        await connection.execute(
            "select count(*) as count from public.drift_alerts where workspace_id=%s and alert_type='drift' and lifecycle in ('open','acknowledged','investigated')",
            (workspace_id,),
        )
    ).fetchone()
    reports = await (
        await connection.execute(
            "select count(distinct email_id) as count from public.verification_reports r where workspace_id=%s and exists(select 1 from public.emails e where e.id=r.email_id and e.workspace_id=r.workspace_id and e.deleted_at is null)",
            (workspace_id,),
        )
    ).fetchone()
    failures = await (
        await connection.execute(
            # Emails whose latest job failed: the same set the inbox's `failed` filter shows, so the
            # number and the list it links to agree. A failure that a later retry fixed is not counted.
            """select count(*) as count from public.emails n
            join lateral (select state from public.processing_jobs
                          where workspace_id=n.workspace_id and email_id=n.id
                          order by created_at desc limit 1) j on true
            where n.workspace_id=%s and n.deleted_at is null and j.state='failed'""",
            (workspace_id,),
        )
    ).fetchone()
    baseline = await (
        await connection.execute(
            "select version from public.quality_baselines where workspace_id=%s", (workspace_id,)
        )
    ).fetchone()
    return {
        "emails_total": emails["total"],
        "emails_classified": emails["classified"],
        "cases_open": cases["open"],
        "cases_checked": cases["checked"],
        "cases_failed": cases["failed"],
        "review_queue_size": cases["review"],
        "awaiting_revision": cases["waiting"],
        "emails_unresolved": emails["total"] - emails["classified"],
        "spam_count": emails["spam"],
        "safety_assessed": safety["assessed"],
        "safety_held": safety["held"],
        "document_checks": reports["count"],
        "mismatches": cases["mismatches"],
        "processing_failures": failures["count"],
        "drift_alerts_active": drift["count"] if baseline else None,
        "drift_state": "available" if baseline else "baseline_required",
        "jobs_in_progress": jobs["active"],
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/dashboard")
async def get_dashboard(request: Request, ctx: Viewer):
    async with request.app.state.database.connection() as connection:
        return await workspace_summary(connection, ctx.workspace_id)


class DashboardView(StrictModel):
    sections: list[Literal["attention", "states", "metrics", "guidance", "quality"]] = Field(
        default=["attention", "states", "metrics", "guidance", "quality"], max_length=5
    )

    @model_validator(mode="after")
    def unique(self):
        if len(set(self.sections)) != len(self.sections):
            raise ValueError("Sections must be unique")
        return self


@router.get("/dashboard/preferences")
async def preferences(request: Request, ctx: Viewer):
    async with request.app.state.database.connection() as connection:
        row = await (
            await connection.execute(
                "select widget_config from public.dashboard_preferences where workspace_id=%s and user_id=%s",
                (ctx.workspace_id, ctx.user_id),
            )
        ).fetchone()
    return row["widget_config"] if row else DashboardView().model_dump()


@router.post("/dashboard/preferences")
async def save_preferences(body: DashboardView, request: Request, ctx: Viewer):
    async with request.app.state.database.connection() as connection:
        await connection.execute(
            """insert into public.dashboard_preferences(workspace_id,user_id,widget_config) values(%s,%s,%s)
            on conflict(workspace_id,user_id) do update set widget_config=excluded.widget_config,updated_at=now()""",
            (ctx.workspace_id, ctx.user_id, Jsonb(body.model_dump())),
        )
    return body
