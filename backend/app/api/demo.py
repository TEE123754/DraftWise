import asyncio
from functools import lru_cache

from fastapi import APIRouter, Request, Response
from pydantic import Field

from app.api.dependencies import IdempotencyKey, Operator
from app.domain.errors import DomainError
from app.domain.models import StrictModel
from app.services.dataset_import import build_manifest, open_source
from app.services.demo_sessions import seed_session, token_hash
from app.services.sample_fetch import fetch_sample

router = APIRouter(tags=["demo"])


class SampleFetch(StrictModel):
    email_id: str = Field(default="email_001", pattern=r"^email_[0-9]{3,6}$")
    # AI runs only when the person asks for it; rules are the default.
    prefer_ai: bool = False


@router.post("/demo/gmail/fetch")
async def simulate_fetch(
    body: SampleFetch, request: Request, context: Operator, key: IdempotencyKey
):
    ensure_demo(request)
    if request.headers.get("X-Demo-Mode") != "true":
        raise DomainError("DEMO_REQUIRED", "Open a demo session to use sample fetching", status=403)
    path = request.app.state.settings.demo_dataset_path
    manifest = await asyncio.to_thread(snapshot, path)
    source = open_source(path)
    try:
        async with request.app.state.database.connection() as connection:
            return await fetch_sample(
                connection,
                source,
                manifest,
                context.workspace_id,
                body.email_id,
                key,
                body.prefer_ai,
            )
    finally:
        source.close()


def demo_cookie_options(request) -> dict:
    # An HTTPS frontend on another site (Vercel calling Railway) only keeps and sends the cookie
    # when it is SameSite=None and Secure. Local HTTP development stays Lax.
    if (request.headers.get("origin") or "").startswith("https://"):
        return {"samesite": "none", "secure": True}
    return {"samesite": "lax", "secure": False}


def ensure_demo(request):
    settings = request.app.state.settings
    if not settings.demo_enabled or settings.environment == "production":
        raise DomainError("DEMO_UNAVAILABLE", "Local demo is not enabled", status=404)
    if request.method != "GET" and request.headers.get("origin") not in settings.origins:
        raise DomainError("ORIGIN_FORBIDDEN", "Use the local DraftWise demo page", status=403)


@lru_cache(maxsize=1)
def snapshot(path):
    source = open_source(path)
    try:
        return build_manifest(source)
    finally:
        source.close()


@router.post("/demo/session", status_code=201)
async def start_demo(request: Request, response: Response):
    ensure_demo(request)
    existing = request.cookies.get("draftwise_demo")
    async with request.app.state.database.connection() as connection:
        if existing:
            row = await (
                await connection.execute(
                    "select workspace_id,manifest_sha256 from public.demo_sessions where token_hash=%s and expires_at>now()",
                    (token_hash(existing),),
                )
            ).fetchone()
            if row:
                return {**row, "role": "admin"}
    path = request.app.state.settings.demo_dataset_path
    if not path:
        raise DomainError("DEMO_UNAVAILABLE", "The input bundle is not configured", status=503)
    manifest = await asyncio.to_thread(snapshot, path)
    source = open_source(path)
    try:
        async with request.app.state.database.connection() as connection:
            token, result = await seed_session(
                connection, source, manifest,
                offline_processing=request.app.state.settings.demo_offline_processing,
                max_sessions=request.app.state.settings.demo_max_sessions,
                max_per_hour=request.app.state.settings.demo_max_sessions_per_hour,
            )
    finally:
        source.close()
    response.set_cookie(
        "draftwise_demo",
        token,
        httponly=True,
        max_age=8 * 3600,
        path="/api/v1",
        **demo_cookie_options(request),
    )
    return result


@router.delete("/demo/session")
async def leave_demo(request: Request, response: Response):
    ensure_demo(request)
    token = request.cookies.get("draftwise_demo")
    if token:
        async with request.app.state.database.connection() as connection:
            await connection.execute(
                "update public.demo_sessions set expires_at=now() where token_hash=%s",
                (token_hash(token),),
            )
    response.delete_cookie(
        "draftwise_demo", path="/api/v1", httponly=True, **demo_cookie_options(request)
    )
    return {"state": "ended"}
