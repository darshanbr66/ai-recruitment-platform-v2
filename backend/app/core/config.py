from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, sourced from environment variables / .env.

    Never hardcode secrets here — every sensitive value has no default and
    must come from the environment.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    database_url: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    cors_allow_origins: list[str] = Field(default_factory=list)

    # The candidate-facing frontend's own origin — used to build links a
    # recruiter shares (assessment invitations, campus-drive application
    # links) that resolve on the frontend, not the API. Defaults to the
    # local Vite dev server; production sets this to the deployed frontend
    # URL (e.g. the Vercel domain) via the environment.
    frontend_base_url: str = "http://localhost:5173"

    resume_storage_dir: str = "uploads/resumes"
    max_resume_size_mb: int = 10
    allowed_resume_extensions: tuple[str, ...] = (".pdf", ".doc", ".docx")

    # Resume *file bytes* storage backend (CLAUDE.md § 2: "Resume storage !=
    # DB blob") — see app/integrations/storage. "local" keeps the existing
    # disk-based dev behavior; "mongodb_gridfs" is the production backend,
    # selected via RESUME_STORAGE_PROVIDER on Render (docs/deployment.md
    # § 11). This is independent of MongoDB's *database* config below,
    # which is only meaningful when this is "mongodb_gridfs".
    resume_storage_provider: Literal["local", "mongodb_gridfs"] = "local"

    # MongoDB is used ONLY for resume file bytes via GridFS — never for
    # candidate/application/organization data, which stays in Postgres
    # (CLAUDE.md § 1). Unset by default: a bare `Settings()` for local
    # development on the "local" storage provider must not require a
    # MongoDB deployment to exist.
    mongodb_uri: str | None = None
    mongodb_database: str = "ai_recruitment"

    # Outbound email. Resend (HTTPS) is used when RESEND_API_KEY and EMAIL_FROM
    # are set — it is the production provider, since hosts like Render's free
    # web services block outbound SMTP ports. Otherwise SMTP is used when fully
    # configured (local development). See app/integrations/email/__init__.py.
    # The SMTP password and Resend API key are SecretStr so they can never
    # leak through a repr/log of Settings — each is only unwrapped inside its
    # provider at send time.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_email: str | None = None
    smtp_from_name: str = "AI Recruitment Platform"
    smtp_use_tls: bool = True

    # `email_from` is the Resend sender: a verified-domain address, optionally
    # with a display name, e.g. `SIGVITAS <hr@yourdomain.com>`.
    resend_api_key: SecretStr | None = None
    email_from: str | None = None

    anthropic_api_key: str | None = None
    openai_api_key: str | None = None

    # Free/local AI screening via Ollama (https://ollama.com) — preferred
    # over the paid providers above when explicitly enabled. Unset by
    # default: an unset base URL means "not opted in", not "try
    # localhost and fail" — the base URL is only ever meaningful once
    # someone has actually installed and started Ollama locally.
    ollama_base_url: str | None = None
    ollama_model: str = "llama3.1"

    @model_validator(mode="after")
    def _validate_mongodb_configured_when_selected(self) -> "Settings":
        if self.resume_storage_provider == "mongodb_gridfs" and not self.mongodb_uri:
            raise ValueError(
                "MONGODB_URI is required when RESUME_STORAGE_PROVIDER=mongodb_gridfs."
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    # Required fields are sourced from the environment/.env at runtime, which
    # mypy can't see — hence the targeted ignore rather than making these
    # fields Optional (which would be a lie about their actual contract).
    return Settings()  # type: ignore[call-arg]
