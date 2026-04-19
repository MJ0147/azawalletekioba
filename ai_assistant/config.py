import boto3
import json
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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    OPENAI_API_KEY: str = "missing"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def fetch_db_url_from_aws(cls, v: str) -> str:
        # If v is a Secret Name (not starting with mysql), fetch from AWS
        if v and not v.startswith("mysql"):
            try:
                client = boto3.client("secretsmanager")
                response = client.get_secret_value(SecretId=v)
                secret = json.loads(response["SecretString"])
                return secret.get("DATABASE_URL", v)
            except Exception:
                return v
        return v

    # This tells Pydantic to read from a .env file
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

@lru_cache
def get_settings():
    return Settings()

settings = get_settings()