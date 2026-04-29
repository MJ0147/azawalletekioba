import os
from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Project
    PROJECT_NAME: str = "EKIOBA AI Assistant"
    API_V1_STR: str = "/api/v1"

    # Database — must be a full connection URI supplied via the environment
    DATABASE_URL: str

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
        if not v or "://" not in str(v):
            raise ValueError("DATABASE_URL must be a valid connection URI (e.g. postgresql://user:pass@host/db)")
        return str(v).strip()

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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()