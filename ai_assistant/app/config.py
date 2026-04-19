import boto3
from botocore.exceptions import ClientError
import json
import os
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
    def fetch_db_url_from_aws(cls, v: str) -> str:
        # If v is a Secret Name (not starting with mysql), fetch from AWS
        if v and not v.startswith("mysql"):
            try:
                client = boto3.client("secretsmanager")
                response = client.get_secret_value(SecretId=v)
                secret = json.loads(response["SecretString"])
                return secret.get("DATABASE_URL", v)
            except ClientError as e:
                # Log specific AWS errors (like AccessDenied) to help debug IAM issues
                print(f"Error fetching secret from AWS: {e}")
                return v
        return v

    # This tells Pydantic to read from a .env file
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

@lru_cache
def get_settings():
    return Settings()

settings = get_settings()