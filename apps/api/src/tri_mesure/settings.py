"""Application settings, read from environment variables or a .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_here = Path(__file__).resolve()
# apps/api/src/tri_mesure/settings.py -> repo root; in a container the tree is shallower.
REPO_ROOT = _here.parents[4] if len(_here.parents) > 4 else _here.parents[-1]

ProviderName = Literal["rules", "anthropic", "openai_compat"]
DEV_AUTH_SECRET = "dev-only-secret-change-me-please-32b"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://tri:tri@localhost:5432/tri_mesure"

    llm_provider: ProviderName = "rules"
    llm_model: str = "claude-opus-5-5"

    anthropic_api_key: str | None = None

    openai_compat_base_url: str = "https://api.groq.com/openai/v1"
    openai_compat_api_key: str | None = None
    openai_compat_model: str = "llama-3.1-8b-instant"

    daily_budget_eur: float = 2.0
    usd_to_eur: float = 0.92
    raw_retention_days: int = 30
    web_origin: str = "http://localhost:5173"

    # "dev" allows the default signing secret; "prod" refuses to start with it.
    environment: Literal["dev", "prod"] = "dev"
    # Demo login signs its own tokens (HS256). In production the token would come from the
    # company identity provider (OIDC) and be validated with its public keys instead.
    auth_secret: str = DEV_AUTH_SECRET
    token_ttl_minutes: int = 8 * 60

    # Background AI analysis (outbox-style worker inside the API process).
    worker_enabled: bool = True
    worker_concurrency: int = 4
    worker_poll_seconds: float = 1.0
    worker_max_attempts: int = 3

    @field_validator("auth_secret")
    @classmethod
    def _secret_is_strong_enough(cls, value: str) -> str:
        if not value:  # an empty AUTH_SECRET= line must never mean "sign with an empty key"
            return DEV_AUTH_SECRET
        if len(value) < 32:
            raise ValueError("AUTH_SECRET must be at least 32 characters")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
