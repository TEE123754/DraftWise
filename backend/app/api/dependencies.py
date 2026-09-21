from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.domain.errors import DomainError

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    workspace_id: UUID
    role: str


async def principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    workspace_id: Annotated[UUID | None, Header(alias="X-Workspace-Id")] = None,
) -> Principal:
    if request.headers.get("X-Demo-Mode") == "true":
        from app.api.demo import ensure_demo
        from app.services.demo_sessions import token_hash

        ensure_demo(request)
        token = request.cookies.get("draftwise_demo")
        if not token:
            raise DomainError("AUTH_REQUIRED", "Open the demo to start a session", status=401)
        async with request.app.state.database.connection() as connection:
            cursor = await connection.execute(
                "select workspace_id,actor_id from public.demo_sessions where token_hash=%s and expires_at>now()",
                (token_hash(token),),
            )
            demo = await cursor.fetchone()
        if demo is None:
            raise DomainError(
                "AUTH_REQUIRED", "Demo session expired. Open the demo again.", status=401
            )
        if workspace_id != demo["workspace_id"]:
            raise DomainError(
                "FORBIDDEN", "This workspace does not belong to the demo session", status=403
            )
        return Principal(demo["actor_id"], demo["workspace_id"], "admin")
    if credentials is None or workspace_id is None:
        raise DomainError("AUTH_REQUIRED", "Sign in and select a workspace", status=401)
    user_id = await request.app.state.auth.verify(credentials.credentials)
    async with request.app.state.database.connection() as connection:
        cursor = await connection.execute(
            "select role from public.memberships where workspace_id=%s and user_id=%s",
            (workspace_id, user_id),
        )
        membership = await cursor.fetchone()
    if membership is None:
        raise DomainError("FORBIDDEN", "Workspace membership is required", status=403)
    return Principal(user_id, workspace_id, membership["role"])


def require_roles(*roles: str):
    async def dependency(context: Annotated[Principal, Depends(principal)]):
        if context.role not in roles:
            raise DomainError(
                "FORBIDDEN", "Your workspace role does not permit this action", status=403
            )
        return context

    return dependency


Viewer = Annotated[Principal, Depends(principal)]
Operator = Annotated[Principal, Depends(require_roles("operator", "reviewer", "admin"))]
Reviewer = Annotated[Principal, Depends(require_roles("reviewer", "admin"))]
Admin = Annotated[Principal, Depends(require_roles("admin"))]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]
