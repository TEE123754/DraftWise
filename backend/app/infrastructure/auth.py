import asyncio
from uuid import UUID

import jwt

from app.config import Settings
from app.domain.errors import DomainError


class TokenVerifier:
    def __init__(self, settings: Settings):
        self.issuer = settings.supabase_jwt_issuer or f"{settings.supabase_url.rstrip('/')}/auth/v1"
        self.audience = settings.supabase_jwt_audience
        self.jwks = (
            jwt.PyJWKClient(
                f"{self.issuer}/.well-known/jwks.json", cache_keys=True, lifespan=300, timeout=5
            )
            if settings.supabase_url
            else None
        )

    async def verify(self, token: str) -> UUID:
        if self.jwks is None:
            raise DomainError(
                "AUTH_UNAVAILABLE", "Supabase authentication is not configured", status=503
            )
        try:
            key = await asyncio.to_thread(self.jwks.get_signing_key_from_jwt, token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256", "ES256"],
                issuer=self.issuer,
                audience=self.audience,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
            return UUID(claims["sub"])
        except (jwt.PyJWTError, ValueError, KeyError) as exc:
            raise DomainError(
                "AUTH_REQUIRED", "Your session is invalid or expired", status=401
            ) from exc
