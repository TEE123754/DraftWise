from urllib.parse import quote

import httpx

from app.config import Settings
from app.domain.errors import DomainError


class Storage:
    def __init__(self, settings: Settings):
        self.settings = settings

    def headers(self):
        key = self.settings.supabase_service_role_key
        if not key or not self.settings.supabase_url:
            raise DomainError(
                "STORAGE_UNAVAILABLE", "Supabase private storage is not configured", status=503
            )
        value = key.get_secret_value()
        headers = {"apikey": value}
        if not value.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {value}"
        return headers

    def url(self, key: str, operation: str = "object"):
        return f"{self.settings.supabase_url.rstrip('/')}/storage/v1/{operation}/{quote(self.settings.storage_bucket, safe='')}/{quote(key, safe='/')}"

    def configured(self) -> bool:
        return bool(self.settings.supabase_service_role_key and self.settings.supabase_url)

    async def delete(self, key: str) -> None:
        """Remove one uploaded object. One that is already gone counts as removed, so a retry is always safe."""
        if key.startswith(("demo-seed/", "linked-source/")):
            raise DomainError("STORAGE_KEY_NOT_PHYSICAL", "This key is not an uploaded object", status=400)
        async with httpx.AsyncClient(timeout=30) as client:
            result = await client.delete(self.url(key), headers=self.headers())
        if result.status_code != 404 and not result.is_success:
            raise DomainError("STORAGE_UNAVAILABLE", "Storage did not delete the object", retryable=True, status=503)

    async def reserve(self, key: str) -> str:
        async with httpx.AsyncClient(timeout=15) as client:
            result = await client.post(
                self.url(key, "object/upload/sign"), headers=self.headers(), json={}
            )
            if not result.is_success:
                raise DomainError(
                    "STORAGE_UNAVAILABLE", "Could not reserve a private upload", status=503
                )
            signed = result.json()["url"] if "url" in result.json() else result.json()["signedURL"]
            if signed.startswith("/object/"):
                return f"{self.settings.supabase_url.rstrip('/')}/storage/v1{signed}"
            if signed.startswith("/storage/v1/"):
                return f"{self.settings.supabase_url.rstrip('/')}{signed}"
            raise DomainError(
                "STORAGE_UNAVAILABLE", "Storage returned an invalid upload URL", status=503
            )

    async def download(self, key: str) -> bytes:
        while key.startswith("linked-source/"):
            key = key.split("/", 3)[3]
        if key.startswith("demo-seed/"):
            from app.services.dataset_import import open_source

            if not self.settings.demo_enabled or self.settings.environment == "production":
                raise DomainError("DEMO_UNAVAILABLE", "Demo source is unavailable", status=404)
            parts = key.split("/", 3)
            if len(parts) != 4:
                raise DomainError("DEMO_UNAVAILABLE", "Invalid demo source", status=404)
            source = open_source(self.settings.demo_dataset_path)
            try:
                return source.read(parts[3])
            finally:
                source.close()
        async with httpx.AsyncClient(timeout=30) as client:
            async with client.stream("GET", self.url(key), headers=self.headers()) as result:
                if not result.is_success:
                    raise DomainError(
                        "UPLOAD_PENDING", "Uploaded bytes are not available", status=409
                    )
                data = bytearray()
                async for chunk in result.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > self.settings.max_upload_bytes:
                        raise DomainError(
                            "FILE_LIMIT_EXCEEDED",
                            "Uploaded file exceeds the size limit",
                            status=413,
                        )
                return bytes(data)
