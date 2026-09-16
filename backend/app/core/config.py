from functools import lru_cache

from pydantic import Field
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

    resume_storage_dir: str = "uploads/resumes"
    max_resume_size_mb: int = 10
    allowed_resume_extensions: tuple[str, ...] = (".pdf", ".doc", ".docx")

    resend_api_key: str | None = None
    email_from: str | None = None

    anthropic_api_key: str | None = None
    openai_api_key: str | None = None

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    # Required fields are sourced from the environment/.env at runtime, which
    # mypy can't see — hence the targeted ignore rather than making these
    # fields Optional (which would be a lie about their actual contract).
    return Settings()  # type: ignore[call-arg]
