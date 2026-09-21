import json
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Request
from psycopg.types.json import Jsonb
from pydantic import Field

from app.api.dependencies import Reviewer, Viewer
from app.domain.errors import DomainError
from app.domain.models import EmailCategory, StrictModel
from app.services.drift_detection import monitor
from app.services.quality import distribution

router = APIRouter(tags=["quality"])


class ReviewLabel(StrictModel):
    category: EmailCategory
    reason: str = Field(min_length=5, max_length=1000)


@router.post("/emails/{email_id}/classification-review")
async def review_label(email_id: UUID, body: ReviewLabel, request: Request, ctx: Reviewer):
    async with request.app.state.database.connection() as connection:
        email = await (
            await connection.execute(
                "select id from public.emails where workspace_id=%s and id=%s and deleted_at is null for update",
                (ctx.workspace_id, email_id),
            )
        ).fetchone()
        if not email:
            raise DomainError("NOT_FOUND", "Email was not found", status=404)
        await connection.execute(
            """insert into public.email_classifications(workspace_id,email_id,revision,category,ambiguous,confidence,decided_by,evidence,run_metadata)
            select %s,%s,coalesce(max(revision),0)+1,%s,false,1,'human','[]',%s from public.email_classifications where workspace_id=%s and email_id=%s""",
            (
                ctx.workspace_id,
                email_id,
                body.category,
                Jsonb(
                    {
                        "method": "human_review",
                        "reviewer_id": str(ctx.user_id),
                        "reason": body.reason,
                    }
                ),
                ctx.workspace_id,
                email_id,
            ),
        )
    return {"state": "reviewed"}


@router.post("/quality/baseline")
async def baseline(request: Request, ctx: Reviewer):
    async with request.app.state.database.connection() as connection:
        rows = await (
            await connection.execute(
                """select h.category,p.category as predicted from
            (select distinct on(email_id) * from public.email_classifications where workspace_id=%s and decided_by='human' order by email_id,revision desc)h
            left join lateral(select category from public.email_classifications where workspace_id=h.workspace_id and email_id=h.email_id
            and revision<h.revision and decided_by<>'human' order by revision desc limit 1)p on true""",
                (ctx.workspace_id,),
            )
        ).fetchall()
        if len(rows) < 20:
            raise DomainError(
                "INSUFFICIENT_LABELS",
                f"Review at least 20 distinct emails before creating a baseline. Currently {len(rows)}.",
                status=409,
            )
        paired = [r for r in rows if r["predicted"] is not None]
        reference = {
            "distribution": distribution([r["category"] for r in rows]),
            "sample_count": len(rows),
            "error_rate": sum(r["predicted"] != r["category"] for r in paired) / len(paired)
            if paired
            else None,
        }
        version = str(uuid4())
        await connection.execute(
            """insert into public.quality_baselines(workspace_id,version,reference_data,created_by)
            values(%s,%s,%s,%s) on conflict(workspace_id) do update set version=excluded.version,reference_data=excluded.reference_data,
            created_by=excluded.created_by,created_at=now()""",
            (ctx.workspace_id, version, Jsonb(reference), ctx.user_id),
        )
    return {"version": version, **reference}


@router.get("/quality/monitor")
async def quality_status(request: Request, ctx: Viewer):
    async with request.app.state.database.connection() as connection:
        # Assessment can persist a deduplicated workspace alert; no external effects.
        return await monitor(connection, ctx.workspace_id)


ARTIFACTS = Path(__file__).resolve().parents[3] / "artifacts"
# The measured results shipped with the application (backend/data), so a deployed instance can show
# them. Only aggregate results are kept there: no per-email predictions and no answer key.
DATA = Path(__file__).resolve().parents[2] / "data"
BENCHMARK_REPORT = ARTIFACTS / "quality/report-v2.json"
SHIPPED_BENCHMARK_REPORT = DATA / "quality/report-v2.json"
# Runs of `scripts/benchmark.py run --submit` against the organizer scoring server, saved as
# artifacts/benchmarks/organizer-eval-NN; the highest number is the latest. The scoreboard and
# manifest of a run are copied to backend/data/benchmarks so that deployed instances have them too.
BENCHMARKS = ARTIFACTS / "benchmarks"
SHIPPED_BENCHMARKS = DATA / "benchmarks"


def benchmark_report_path() -> Path:
    """The local report if this checkout has one, otherwise the copy shipped with the application."""
    return BENCHMARK_REPORT if BENCHMARK_REPORT.is_file() else SHIPPED_BENCHMARK_REPORT


def latest_official_run() -> Path | None:
    # A local run of the same name wins over the shipped copy; the highest name is the latest.
    found = {}
    for root in (SHIPPED_BENCHMARKS, BENCHMARKS):
        for path in root.glob("organizer-eval-*"):
            if (path / "scoreboard.json").is_file():
                found[path.name] = path
    return found[max(found)] if found else None


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


@router.get("/quality/benchmark")
async def get_quality_benchmark(request: Request, ctx: Viewer):
    # Only measured results are ever returned: no placeholder metrics when they are absent
    # (the artifacts folder is not shipped in container images).
    report = read_json(benchmark_report_path())
    if report is None:
        raise DomainError(
            "BENCHMARK_UNAVAILABLE",
            "No benchmark report is available in this environment.",
            status=404,
        )
    run = latest_official_run()
    scoreboard = read_json(run / "scoreboard.json") if run else None
    manifest = (read_json(run / "manifest.json") if run else None) or {}
    report["official"] = (
        {
            "scoreboard": scoreboard,
            "run": run.name,
            "emails": manifest.get("emails_count"),
            "unresolved": len(manifest.get("unresolved_classification", [])),
            # None for runs made before the mode was recorded: AI use is then unknown.
            "ai_fallback": manifest.get("ai_fallback"),
        }
        if scoreboard
        else None
    )
    settings = request.app.state.settings
    model = getattr(settings, f"{settings.ai_provider}_model", "") or "default"
    report.setdefault("reference", {"source": "unknown", "independent": False})
    report["provider"] = {
        "name": settings.ai_provider,
        "model": model,
        "timeout_seconds": settings.ai_timeout_seconds,
        "extraction_timeout_seconds": settings.ai_extraction_timeout_seconds,
    }
    return report
