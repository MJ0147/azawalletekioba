import os
from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Project Settings
    PROJECT_NAME: str = "EKIOBA AI Assistant"
    API_V1_STR: str = "/api/v1"
    
    # Database provider — set AZURE_DATABASE_URL for Azure SQL/PostgreSQL
    AZURE_DATABASE_URL: str = ""
    DATABASE_URL: str = ""
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    OPENAI_API_KEY: str = "missing"
    COPILOT_API_KEY: str = ""
    COPILOT_BASE_URL: str = "https://models.inference.ai.azure.com"
    COPILOT_MODEL: str = "gpt-4o-mini"

    @field_validator("COPILOT_API_KEY", mode="before")
    @classmethod
    def fallback_copilot_key(cls, v: str) -> str:
        if v:
            return v
        return os.getenv("COPILOT_API_KEY") or os.getenv("GITHUB_TOKEN") or os.getenv("OPENAI_API_KEY") or ""

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        azure_url = (os.getenv("AZURE_DATABASE_URL") or "").strip()
        primary_url = str(v or "").strip()
        resolved = primary_url or azure_url
        if not resolved or "://" not in resolved:
            raise ValueError(
                "Provide a valid database URI via DATABASE_URL or AZURE_DATABASE_URL."
            )
        return resolved

    # This tells Pydantic to read from a .env file
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

@lru_cache
def get_settings():
    return Settings()

settings = get_settings()