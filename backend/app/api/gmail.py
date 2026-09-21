import base64
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.api.dependencies import Reviewer, Viewer
from app.domain.errors import DomainError

router = APIRouter(tags=["gmail"])

DEMO_MESSAGE = (
    "Gmail import is not available in demo mode. "
    "Use manual email intake or the sample inbox meanwhile."
)
UNCONFIGURED_MESSAGE = (
    "Google OAuth is not configured on this server. "
    "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in backend configuration to enable live Gmail sync."
)

OAUTH_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_PROFILE_URL = "https://gmail.googleapis.com/gmail/v1/users/me/profile"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


def _signing_key(request: Request) -> bytes:
    secret = request.app.state.settings.google_client_secret
    if secret:
        return secret.get_secret_value().encode("utf-8")
    return b"draftwise-oauth-state-signing-key"


def _generate_state(request: Request, workspace_id: UUID, user_id: UUID) -> str:
    payload = {
        "workspace_id": str(workspace_id),
        "user_id": str(user_id),
        "ts": int(time.time()),
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(_signing_key(request), raw, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw + b"." + sig).decode("ascii")


def _verify_state(request: Request, state_str: str) -> dict:
    try:
        data = base64.urlsafe_b64decode(state_str.encode("ascii"))
        raw, sig = data.rsplit(b".", 1)
        expected = hmac.new(_signing_key(request), raw, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("Invalid signature")
        payload = json.loads(raw.decode("utf-8"))
        if time.time() - payload.get("ts", 0) > 600:  # 10 min TTL
            raise ValueError("State expired")
        return payload
    except Exception:
        raise DomainError("INVALID_STATE", "OAuth state is invalid or expired. Please retry.", status=400)


@router.get("/gmail/connections")
async def get_connections(request: Request, ctx: Viewer):
    is_demo = request.headers.get("X-Demo-Mode") == "true"
    settings = request.app.state.settings
    configured = bool(settings.google_client_id and settings.google_client_secret)

    if is_demo:
        return {
            "items": [],
            "available": False,
            "configured": False,
            "message": DEMO_MESSAGE,
        }

    if not configured:
        return {
            "items": [],
            "available": False,
            "configured": False,
            "message": UNCONFIGURED_MESSAGE,
        }

    async with request.app.state.database.connection() as connection:
        rows = await (
            await connection.execute(
                """select id, workspace_id, email, state, messages_imported,
                          last_sync_at, last_error, created_at, updated_at
                   from public.mailbox_connections
                   where workspace_id = %s
                   order by created_at desc""",
                (ctx.workspace_id,),
            )
        ).fetchall()

    return {
        "items": [
            {
                "id": str(r["id"]),
                "workspace_id": str(r["workspace_id"]),
                "email": r["email"],
                "state": r["state"],
                "messages_imported": r["messages_imported"],
                "last_sync_at": r["last_sync_at"].isoformat() if r["last_sync_at"] else None,
                "last_error": r["last_error"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ],
        "available": True,
        "configured": True,
        "message": None,
    }


@router.get("/gmail/connect")
async def connect(request: Request, ctx: Reviewer):
    is_demo = request.headers.get("X-Demo-Mode") == "true"
    settings = request.app.state.settings
    configured = bool(settings.google_client_id and settings.google_client_secret)

    if is_demo:
        raise DomainError("GMAIL_UNAVAILABLE", DEMO_MESSAGE, status=503)

    if not configured:
        raise DomainError("GMAIL_UNAVAILABLE", UNCONFIGURED_MESSAGE, status=503)

    state = _generate_state(request, ctx.workspace_id, ctx.user_id)
    redirect_uri = f"{request.base_url}api/v1/gmail/callback"
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GMAIL_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    auth_url = f"{OAUTH_AUTH_URL}?{urlencode(params)}"
    return {"auth_url": auth_url, "state": state}


@router.get("/gmail/callback")
async def callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    settings = request.app.state.settings
    site_url = settings.site_url.rstrip("/")

    if error:
        return RedirectResponse(f"{site_url}/settings/connections?error={error}")

    if not code or not state:
        raise DomainError("INVALID_CALLBACK", "Missing authorization code or state", status=400)

    state_data = _verify_state(request, state)
    workspace_id = UUID(state_data["workspace_id"])
    user_id = UUID(state_data["user_id"])
    redirect_uri = f"{request.base_url}api/v1/gmail/callback"

    # Exchange authorization code for tokens
    async with httpx.AsyncClient(timeout=15.0) as client:
        token_resp = await client.post(
            OAUTH_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret.get_secret_value() if settings.google_client_secret else "",
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            return RedirectResponse(f"{site_url}/settings/connections?error=token_exchange_failed")
        token_data = token_resp.json()
        access_token = token_data.get("access_token", "")
        refresh_token = token_data.get("refresh_token", "")

        # Fetch authorized email address
        profile_resp = await client.get(
            GMAIL_PROFILE_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if profile_resp.status_code != 200:
            return RedirectResponse(f"{site_url}/settings/connections?error=profile_fetch_failed")
        email_address = profile_resp.json().get("emailAddress", "unknown@gmail.com")

    async with request.app.state.database.connection() as connection:
        await connection.execute(
            """insert into public.mailbox_connections(
                 workspace_id, owner_user_id, email, state, access_token, refresh_token, updated_at
               ) values (%s, %s, %s, 'active', %s, %s, now())
               on conflict (workspace_id, email) do update set
                 state = 'active',
                 access_token = excluded.access_token,
                 refresh_token = case when excluded.refresh_token <> '' then excluded.refresh_token else public.mailbox_connections.refresh_token end,
                 last_error = null,
                 updated_at = now()""",
            (workspace_id, user_id, email_address, access_token, refresh_token),
        )

    return RedirectResponse(f"{site_url}/settings/connections?connected=true&email={email_address}")


@router.post("/gmail/connections/{connection_id}/sync")
async def sync_connection(connection_id: UUID, request: Request, ctx: Reviewer):
    is_demo = request.headers.get("X-Demo-Mode") == "true"
    if is_demo:
        raise DomainError("GMAIL_UNAVAILABLE", DEMO_MESSAGE, status=503)

    async with request.app.state.database.connection() as connection:
        conn = await (
            await connection.execute(
                "select id, email from public.mailbox_connections where workspace_id = %s and id = %s",
                (ctx.workspace_id, connection_id),
            )
        ).fetchone()
        if not conn:
            raise DomainError("NOT_FOUND", "Mailbox connection not found", status=404)

        await connection.execute(
            "update public.mailbox_connections set state = 'syncing', updated_at = now() where id = %s",
            (connection_id,),
        )

    return {"status": "sync_initiated", "connection_id": str(connection_id)}


@router.delete("/gmail/connections/{connection_id}")
async def disconnect_connection(connection_id: UUID, request: Request, ctx: Reviewer):
    is_demo = request.headers.get("X-Demo-Mode") == "true"
    if is_demo:
        raise DomainError("GMAIL_UNAVAILABLE", DEMO_MESSAGE, status=503)

    async with request.app.state.database.connection() as connection:
        res = await connection.execute(
            "update public.mailbox_connections set state = 'disconnected', access_token = '', updated_at = now() where workspace_id = %s and id = %s",
            (ctx.workspace_id, connection_id),
        )
        if res.rowcount == 0:
            raise DomainError("NOT_FOUND", "Mailbox connection not found", status=404)

    return {"status": "disconnected", "connection_id": str(connection_id)}
