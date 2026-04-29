import os
from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Project
    PROJECT_NAME: str = "EKIOBA AI Assistant"
    API_V1_STR: str = "/api/v1"

    # Database provider selection: auto | azure | digitalocean
    DATABASE_PROVIDER: str = "auto"
    AZURE_DATABASE_URL: str = ""
    DIGITALOCEAN_DATABASE_URL: str = ""
    DATABASE_URL: str = ""

    # Auth — must be a strong secret, at least 32 characters
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS — comma-separated list of allowed origins (e.g. "https://ekioba.com,http://localhost:3000")
    CORS_ORIGINS: str = "http://localhost:3000"

    # AI / Copilot integration
    COPILOT_API_KEY: str = ""
    COPILOT_BASE_URL: str = "https://models.inference.ai.azure.com"
    COPILOT_MODEL: str = "gpt-4o-mini"

    # External integrations
    TELEGRAM_BOT_TOKEN: str = ""
    GEMINI_API_KEY: str = ""

    # ── Validators ──────────────────────────────────────────────────────────

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def secret_key_strength(cls, v: str) -> str:
        if not v or len(v.strip()) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        provider = (os.getenv("DATABASE_PROVIDER") or "auto").strip().lower()
        azure_url = (os.getenv("AZURE_DATABASE_URL") or "").strip()
        do_url = (os.getenv("DIGITALOCEAN_DATABASE_URL") or "").strip()
        primary_url = str(v or "").strip()

        if provider not in {"auto", "azure", "digitalocean", "do"}:
            raise ValueError("DATABASE_PROVIDER must be one of: auto, azure, digitalocean")

        if provider == "azure":
            resolved = azure_url or primary_url
        elif provider in {"digitalocean", "do"}:
            resolved = do_url or primary_url
        else:
            if primary_url:
                resolved = primary_url
            elif azure_url and do_url:
                raise ValueError(
                    "Both AZURE_DATABASE_URL and DIGITALOCEAN_DATABASE_URL are set. "
                    "Set DATABASE_PROVIDER to select one."
                )
            else:
                resolved = azure_url or do_url

        if not resolved or "://" not in resolved:
            raise ValueError(
                "Provide a valid database URI via DATABASE_URL, or set DATABASE_PROVIDER with "
                "AZURE_DATABASE_URL / DIGITALOCEAN_DATABASE_URL"
            )
        return resolved

    @field_validator("COPILOT_API_KEY", mode="before")
    @classmethod
    def fallback_copilot_key(cls, v: str) -> str:
        if v:
            return v
        return os.getenv("GITHUB_TOKEN") or os.getenv("OPENAI_API_KEY") or ""

    # ── Helpers ─────────────────────────────────────────────────────────────

    def cors_origins_list(self) -> List[str]:
        """Return CORS_ORIGINS as a list, stripping whitespace."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

# ...existing code...
@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
# ...existing code...