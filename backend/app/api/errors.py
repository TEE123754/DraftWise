import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg import OperationalError
from psycopg_pool import PoolTimeout
from starlette.exceptions import HTTPException

from app.domain.errors import DomainError

logger = logging.getLogger(__name__)


def response(request: Request, status: int, code: str, message: str, retryable: bool = False):
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": getattr(request.state, "request_id", str(uuid4())),
                "retryable": retryable,
                "details": {},
            }
        },
        headers={"Retry-After": "60"} if status == 429 else None,
    )


def install_errors(app: FastAPI):
    @app.middleware("http")
    async def request_id(request, call_next):
        request.state.request_id = str(uuid4())
        result = await call_next(request)
        result.headers["X-Request-Id"] = request.state.request_id
        return result

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return response(request, exc.status, exc.code, exc.message, exc.retryable)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return response(request, 422, "VALIDATION_ERROR", "Request fields are missing or invalid")

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return response(
            request, exc.status_code, "HTTP_ERROR", "The requested operation is unavailable"
        )

    @app.exception_handler(OperationalError)
    @app.exception_handler(PoolTimeout)
    async def unavailable(request, exc):
        return response(
            request, 503, "DATABASE_UNAVAILABLE", "Storage is temporarily unavailable", True
        )

    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        logger.error(
            "Unexpected request failure request_id=%s type=%s",
            request.state.request_id,
            type(exc).__name__,
        )
        return response(request, 500, "INTERNAL_ERROR", "The request could not be completed")
