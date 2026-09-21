from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_BACKEND_DIR / ".env"), extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: SecretStr | None = None
    supabase_url: str = ""
    storage_bucket: str = "shipping-originals"
    supabase_service_role_key: SecretStr | None = None
    supabase_jwt_issuer: str = ""
    supabase_jwt_audience: str = "authenticated"
    gemini_api_key: SecretStr | None = None
    ai_provider: Literal["gemini", "morpheus"] = "gemini"
    morpheus_api_key: SecretStr | None = None
    morpheus_base_url: Literal["https://api.mor.org/api/v1"] = "https://api.mor.org/api/v1"
    morpheus_model: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"
    free_only: bool = True
    demo_enabled: bool = False
    demo_dataset_path: str = ""
    # Read and compare every seeded comparison email's documents in the background (rules only).
    demo_offline_processing: bool = True
    demo_ai_enabled: bool = True
    demo_ai_call_limit: int = Field(default=9, ge=0, le=30)
    # Live AI calls one workspace may make per day. Demo sessions have their own, smaller allowance.
    ai_daily_budget: int = Field(default=30, ge=0, le=10_000)
    # Pause between calls of a live evaluation: the provider rate-limits bursts.
    ai_eval_pause_seconds: float = Field(default=4.0, ge=0, le=60)
    ai_timeout_seconds: int = Field(default=25, ge=1, le=60)
    ai_extraction_timeout_seconds: int = Field(default=60, ge=1, le=90)
    # Google OAuth (required for Gmail connection feature)
    google_client_id: str = ""
    google_client_secret: SecretStr | None = None
    # Fernet key that encrypts stored Gmail OAuth tokens. Gmail cannot be connected without it.
    # Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    token_encryption_key: SecretStr | None = None
    # Public site URL used in emails and sitemap
    site_url: str = "http://localhost:3000"
    allowed_origins: str = "http://localhost:3000"
    max_upload_bytes: int = Field(default=20 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)
    max_pdf_pages: int = Field(default=20, ge=1, le=100)
    max_xlsx_cells: int = Field(default=100_000, ge=1, le=500_000)
    max_prompt_chars: int = Field(default=50_000, ge=1000, le=100_000)
    parse_timeout_seconds: int = Field(default=30, ge=1, le=120)
    ocr_languages: str = "eng"
    # Absolute path to tesseract.exe on hosts where it is not on PATH (read from backend/.env).
    tesseract_cmd: str = ""
    # AI extraction fallback runs only when at least this many of the 7 fields are missing.
    ai_fallback_min_missing: int = Field(default=3, ge=1, le=7)
    policy_version: Literal["v1"] = "v1"
    preview_ttl_seconds: int = Field(default=1800, ge=60, le=1800)
    # Jobs are I/O bound (a hosted database costs ~100 ms a statement); leases and fencing make
    # concurrent slots safe.
    worker_concurrency: int = Field(default=3, ge=1, le=8)
    provider_concurrency: int = Field(default=2, ge=1, le=2)

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        # Explicit test settings must never inherit live credentials or feature flags.
        if init_settings.init_kwargs.get("environment") == "test":
            return (init_settings,)
        return init_settings, env_settings, dotenv_settings, file_secret_settings

    @model_validator(mode="after")
    def resolve_dataset_path(self):
        if self.demo_dataset_path:
            path = Path(self.demo_dataset_path).expanduser()
            self.demo_dataset_path = str((path if path.is_absolute() else _BACKEND_DIR / path).resolve())
        return self

    @model_validator(mode="after")
    def production_configuration(self):
        if self.environment == "production":
            if not self.database_url or not self.supabase_url.startswith("https://"):
                raise ValueError("Production requires DATABASE_URL and an HTTPS SUPABASE_URL")
            if any(not origin.startswith("https://") for origin in self.origins):
                raise ValueError("Production CORS origins must use HTTPS")
        return self

    @property
    def origins(self) -> list[str]:
        return [
            origin.strip().rstrip("/")
            for origin in self.allowed_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
