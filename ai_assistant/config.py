from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Project Settings
    PROJECT_NAME: str = "EKIOBA AI Assistant"
    API_V1_STR: str = "/api/v1"
    
    # Database & Security (Values provided via .env)
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 70

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        # Keep DATABASE_URL as provided from env/.env; do not resolve cloud secrets.
        if not v:
            return v

        normalized = str(v).strip().lower()
        if "://" in normalized:
            return v

        if normalized.startswith(("mysql", "postgres", "postgresql", "sqlite", "mssql", "oracle", "redis", "rediss")):
            return v

        return v

    # This tells Pydantic to read from a .env file
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

@lru_cache
def get_settings():
    return Settings()

settings = get_settings()