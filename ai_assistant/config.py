from functools import lru_cache
from typing import List

from pydantic import ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Project
    PROJECT_NAME: str = "Iyobo AI (Aza AI) — EKIOBA"
    API_V1_STR: str = "/api/v1"

    # Database — Supabase Postgres connection string (Supabase -> Connect).
    # DATABASE_URL falls back to SUPABASE_DB_URL, so one connection string is enough. From networks
    # without IPv6, use the Session pooler string (…pooler.supabase.com:5432), not the direct host.
    DATABASE_URL: str = ""
    SUPABASE_DB_URL: str = ""

    # Auth — must be a strong secret, at least 32 characters
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS — comma-separated list of allowed origins (e.g. "https://beninkingdom.online,http://localhost:3000")
    CORS_ORIGINS: str = "http://localhost:3000"

    # AI — xAI Grok is the only AI provider. It answers from the Knowledge Base first
    # and uses its web search tool to fill gaps.
    XAI_API_KEY: str = ""
    XAI_BASE_URL: str = "https://api.x.ai/v1"
    # Must be a model this xAI team can actually reach. A name the account has no access to
    # fails every chat with a 404, which surfaces only as "AI Service unreachable".
    # Check with: curl https://api.x.ai/v1/models -H "Authorization: Bearer $XAI_API_KEY"
    XAI_MODEL: str = "grok-4.5"
    XAI_WEB_SEARCH: bool = True
    XAI_TIMEOUT_SECONDS: float = 60.0
    # Everything found on the web is checked against the Knowledge Base before it is used
    # (app/web_verification.py). Web claims the Knowledge Base contradicts are always dropped. Web
    # claims it doesn't cover are passed on labelled as unverified; set true to drop those too.
    WEB_REQUIRE_KB_CONFIRMATION: bool = False

    # Knowledge Base — Iyobo's main source. Leave KNOWLEDGE_BASE_DIR empty to use the repo's
    # "Knowledge Base" folder, or /app/knowledge_base when mounted into the container.
    KNOWLEDGE_BASE_DIR: str = ""
    # Comma-separated files/folders (relative to the Knowledge Base root) kept away from the
    # public assistant: internal infrastructure, and anything written for whoever builds EKIOBA
    # rather than for a visitor. Keep this in step with EXCLUDE in scripts/sync_knowledge_base.py.
    KNOWLEDGE_BASE_EXCLUDE: str = "SECURITY.md,DEPLOYMENT.md,Supabase,README.md,AGENT_INSTRUCTIONS.md,WALLET_DASHBOARD_INTEGRATION.md,Project Readmes"
    KNOWLEDGE_BASE_TOP_K: int = 6
    KNOWLEDGE_BASE_MAX_CHARS: int = 12000

    # Learning — Iyobo remembers each user and queues what users teach it for the owner's approval.
    # Where conversations, user memory and the review queue are stored. Empty = DATABASE_URL.
    # PostgreSQL tables go in the private `iyobo` schema (Knowledge Base/Supabase/004_iyobo_memory.sql);
    # a SQLite URL such as sqlite:///./iyobo_memory.db works for local development.
    IYOBO_MEMORY_DB_URL: str = ""
    # Bearer token for the knowledge review endpoints. Empty = those endpoints are closed.
    IYOBO_ADMIN_TOKEN: str = ""
    # Salt for hashing user ids in the review queue. Empty = SECRET_KEY.
    IYOBO_USER_ID_SALT: str = ""
    IYOBO_MAX_SUGGESTIONS_PER_DAY: int = 10

    # External integrations
    TELEGRAM_BOT_TOKEN: str = ""
    # Secret Telegram sends with every webhook delivery; register it with
    # scripts/set_telegram_webhook.py. The webhook refuses all updates while it is empty.
    # Allowed characters: A-Z a-z 0-9 _ - (python -c "import secrets; print(secrets.token_urlsafe(32))").
    TELEGRAM_WEBHOOK_SECRET: str = ""

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

    @field_validator("DATABASE_URL", "SUPABASE_DB_URL", "IYOBO_MEMORY_DB_URL", mode="before")
    @classmethod
    def strip_url(cls, v: str) -> str:
        return str(v or "").strip()

    @model_validator(mode="after")
    def resolve_database_url(self) -> "Settings":
        if not self.DATABASE_URL:
            self.DATABASE_URL = self.SUPABASE_DB_URL
        if "://" not in self.DATABASE_URL:
            raise ValueError(
                "Provide a valid database URI via DATABASE_URL or SUPABASE_DB_URL "
                "(your Supabase Postgres connection string)."
            )
        return self

    # ── Helpers ─────────────────────────────────────────────────────────────

    def cors_origins_list(self) -> List[str]:
        """Return CORS_ORIGINS as a list, stripping whitespace."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    def knowledge_base_exclude_list(self) -> List[str]:
        """Return KNOWLEDGE_BASE_EXCLUDE as a list, stripping whitespace."""
        return [p.strip() for p in self.KNOWLEDGE_BASE_EXCLUDE.split(",") if p.strip()]

    def memory_database_url(self) -> str:
        """Where Iyobo stores conversations, user memory and the review queue."""
        return self.IYOBO_MEMORY_DB_URL or self.DATABASE_URL

    def user_id_salt(self) -> str:
        return self.IYOBO_USER_ID_SALT or self.SECRET_KEY

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Build the settings, naming any missing ones.

    Settings are read at import time, so a missing required value crashes the process before it can
    serve or log anything useful. On a platform that only reports "function invocation failed" that
    is very hard to diagnose, so spell out exactly which variables to set.
    """
    try:
        return Settings()  # pyright: ignore[reportCallIssue]
    except ValidationError as exc:
        missing = sorted({
            str(error["loc"][0])
            for error in exc.errors()
            if error.get("type") == "missing" and error.get("loc")
        })
        # A rule that rejected a value says what it wants in its own message; pass those through
        # too, or a bad DATABASE_URL still reaches the log as a bare pydantic traceback.
        complaints = [
            str(error.get("msg", "")).removeprefix("Value error, ").rstrip(".") + "."
            for error in exc.errors()
            if error.get("type") != "missing"
        ]
        if not missing and not complaints:
            raise
        problems = []
        if missing:
            problems.append("Not set: " + ", ".join(missing) + ".")
        problems.extend(complaints)
        raise RuntimeError(
            "Iyobo's assistant can't start. " + " ".join(problems)
            + " Set these in the environment (on Vercel: the iyobo service's Environment"
            + " Variables; locally: ai_assistant/.env). It needs SECRET_KEY, at least 32"
            + " characters, and DATABASE_URL (or SUPABASE_DB_URL)."
        ) from exc


settings = get_settings()
