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
from app.infrastructure.token_crypto import encryption_configured, seal, unseal

router = APIRouter(tags=["gmail"])

DEMO_MESSAGE = (
    "Gmail import is not available in demo mode. "
    "Use manual email intake or the sample inbox meanwhile."
)
# Signing in to Google and storing the encrypted tokens work, but fetching mail is not built yet.
# Until it is, say so plainly rather than connecting an account that then imports nothing.
# Set this to True in the release that adds fetching.
GMAIL_FETCH_AVAILABLE = False
FUTURE_CODE = "GMAIL_FUTURE_DEVELOPMENT"
FUTURE_MESSAGE = (
    "Fetching mail from Gmail is planned for a future release and is not available yet. "
    "For now, add emails and their documents by upload, or open the demo, which comes with 520 "
    "sample emails."
)
UNCONFIGURED_MESSAGE = (
    "Google OAuth is not configured on this server. "
    "Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and TOKEN_ENCRYPTION_KEY in backend configuration "
    "to enable live Gmail sync."
)

OAUTH_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_PROFILE_URL = "https://gmail.googleapis.com/gmail/v1/users/me/profile"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
OAUTH_REVOKE_URL = "https://oauth2.googleapis.com/revoke"


def _configured(settings) -> bool:
    """Gmail needs the OAuth client and a key to encrypt the tokens it hands back."""
    return bool(settings.google_client_id and settings.google_client_secret) and encryption_configured(settings)


def _signing_key(request: Request) -> bytes:
    secret = request.app.state.settings.google_client_secret
    if not secret:  # never sign with a guessable fallback key
        raise DomainError("GMAIL_UNAVAILABLE", UNCONFIGURED_MESSAGE, status=503)
    return secret.get_secret_value().encode("utf-8")


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
    configured = _configured(settings)

    if is_demo:
        return {
            "items": [],
            "available": False,
            "configured": False,
            "message": DEMO_MESSAGE,
        }

    if GMAIL_FETCH_AVAILABLE and not configured:
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
        # Connections made earlier stay listed so that they can be disconnected and revoked.
        "available": GMAIL_FETCH_AVAILABLE,
        "configured": configured,
        "future": not GMAIL_FETCH_AVAILABLE,
        "message": None if GMAIL_FETCH_AVAILABLE else FUTURE_MESSAGE,
    }


@router.get("/gmail/connect")
async def connect(request: Request, ctx: Reviewer):
    is_demo = request.headers.get("X-Demo-Mode") == "true"
    settings = request.app.state.settings
    configured = _configured(settings)

    if is_demo:
        raise DomainError("GMAIL_UNAVAILABLE", DEMO_MESSAGE, status=503)

    if not GMAIL_FETCH_AVAILABLE:  # do not send anyone to Google to grant access we cannot use yet
        raise DomainError(FUTURE_CODE, FUTURE_MESSAGE, status=501)

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
            (
                workspace_id,
                user_id,
                email_address,
                seal(settings, access_token),
                seal(settings, refresh_token),
            ),
        )

    # The address stays out of the URL (browser history, logs, referrers); the page lists the connection.
    return RedirectResponse(f"{site_url}/settings/connections?connected=true")


@router.post("/gmail/connections/{connection_id}/sync")
async def sync_connection(connection_id: UUID, request: Request, ctx: Reviewer):
    is_demo = request.headers.get("X-Demo-Mode") == "true"
    if is_demo:
        raise DomainError("GMAIL_UNAVAILABLE", DEMO_MESSAGE, status=503)

    if not GMAIL_FETCH_AVAILABLE:  # marking a connection "syncing" would only pretend mail is coming
        raise DomainError(FUTURE_CODE, FUTURE_MESSAGE, status=501)

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
    """Revoke the grant with Google, then erase both tokens. Imported emails are kept."""
    is_demo = request.headers.get("X-Demo-Mode") == "true"
    if is_demo:
        raise DomainError("GMAIL_UNAVAILABLE", DEMO_MESSAGE, status=503)
    settings = request.app.state.settings

    async with request.app.state.database.connection() as connection:
        row = await (
            await connection.execute(
                "select access_token, refresh_token from public.mailbox_connections where workspace_id = %s and id = %s",
                (ctx.workspace_id, connection_id),
            )
        ).fetchone()
    if not row:
        raise DomainError("NOT_FOUND", "Mailbox connection not found", status=404)

    # Revoking the refresh token also ends every access token issued from it.
    token = unseal(settings, row["refresh_token"]) or unseal(settings, row["access_token"])
    revoked = await revoke_token(token) if token else True

    async with request.app.state.database.connection() as connection:
        await connection.execute(
            """update public.mailbox_connections set state = 'disconnected', access_token = '', refresh_token = '',
               last_error = %s, updated_at = now() where workspace_id = %s and id = %s""",
            (None if revoked else "Google did not confirm the revocation", ctx.workspace_id, connection_id),
        )

    return {
        "status": "disconnected",
        "connection_id": str(connection_id),
        "revoked": revoked,
        "message": None
        if revoked
        else "Tokens were erased here, but Google did not confirm the revocation. "
        "Remove DraftWise under Third-party access in your Google Account.",
    }


async def revoke_token(token: str) -> bool:
    """True when Google no longer honours the token, including one that was already revoked or expired."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            result = await client.post(OAUTH_REVOKE_URL, data={"token": token})
    except httpx.HTTPError:
        return False
    if result.status_code == 200:
        return True
    try:
        return result.status_code == 400 and result.json().get("error") == "invalid_token"
    except ValueError:
        return False
