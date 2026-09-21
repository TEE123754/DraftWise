import asyncio
import sys
from contextlib import asynccontextmanager

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    ai_quality,
    alerts,
    amendments,
    cases,
    chat,
    classify,
    dashboard,
    demo,
    document_actions,
    email_actions,
    emails,
    exports,
    extract,
    extraction_review,
    gmail,
    health,
    jobs,
    processing,
    quality,
    rules,
    storage_cleanup,
    uploads,
    verify,
)
from app.api.errors import install_errors
from app.config import Settings, get_settings
from app.infrastructure.auth import TokenVerifier
from app.infrastructure.database import Database
from app.infrastructure.storage import Storage


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    database = Database(settings)

    @asynccontextmanager
    async def lifespan(app):
        await database.open()
        yield
        await database.close()

    app = FastAPI(title="Shipping Amendment Workspace", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.database = database
    app.state.auth = TokenVerifier(settings)
    app.state.storage = Storage(settings)
    app.state.parser_semaphore = asyncio.Semaphore(1)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Workspace-Id",
            "Idempotency-Key",
            "X-Demo-Mode",
        ],
        expose_headers=["Location", "ETag", "X-Request-Id"],
    )
    install_errors(app)
    app.include_router(health.router)
    for module in (
        emails, email_actions, document_actions, classify, extract, extraction_review, verify, jobs, uploads,
        cases, amendments, demo, exports,
        dashboard, chat, alerts, gmail, quality, ai_quality, rules, processing, storage_cleanup,
    ):
        app.include_router(module.router, prefix="/api/v1")
    return app


app = create_app()
