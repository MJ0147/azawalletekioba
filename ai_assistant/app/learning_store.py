"""
Iyobo's knowledge review queue.

When a user teaches Iyobo something (an Edo word, a correction), the agent saves it here as a
pending suggestion. Nothing a user says changes what Iyobo tells other people until the project
owner approves it. Approved suggestions become searchable alongside the Knowledge Base, and
scripts/export_learned_knowledge.py writes them into the Knowledge Base files for the website and
the Supabase vocabulary table.

Works with PostgreSQL (tables in the private `iyobo` schema, see
Knowledge Base/Supabase/004_iyobo_memory.sql) and with SQLite for local development.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

PRIVATE_SCHEMA = "iyobo"

# Generous for real teaching, small enough that one visitor can't flood the queue.
MAX_FIELD_CHARS = {"edo": 120, "english": 200, "category": 40, "example": 400, "note": 1000}
SOURCE_CHANNELS = ("web", "telegram")
STATUSES = ("pending", "approved", "rejected")

metadata = sa.MetaData()

suggestions = sa.Table(
    "knowledge_suggestions",
    metadata,
    sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True, autoincrement=True),
    sa.Column("edo", sa.Text),
    sa.Column("english", sa.Text),
    sa.Column("category", sa.Text),
    sa.Column("example", sa.Text),
    sa.Column("note", sa.Text, nullable=False),
    sa.Column("source_channel", sa.Text, nullable=False, server_default="web"),
    sa.Column("user_ref", sa.Text),
    sa.Column("status", sa.Text, nullable=False, server_default="pending"),
    sa.Column("reviewer_note", sa.Text),
    sa.Column("reviewed_at", sa.DateTime(timezone=True)),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
)


def async_database_url(url: str) -> tuple[str, dict[str, Any]]:
    """Convert a configured database URL into an async SQLAlchemy URL and connection arguments.

    PostgreSQL connections use asyncpg with search_path set to the private `iyobo` schema, so
    nothing is created in the API-exposed `public` schema. SQLite URLs use aiosqlite.
    """
    url = url.strip()
    scheme, _, rest = url.partition("://")
    scheme = scheme.lower()

    if scheme in ("postgres", "postgresql", "postgresql+psycopg2", "postgresql+asyncpg"):
        parts = urlsplit("postgresql+asyncpg://" + rest)
        # asyncpg takes SSL as a connect argument, not an sslmode query parameter.
        query = [(k, v) for k, v in parse_qsl(parts.query) if k.lower() != "sslmode"]
        host = (parts.hostname or "").lower()
        remote = host not in ("localhost", "127.0.0.1", "::1", "db", "postgres")
        connect_args: dict[str, Any] = {"server_settings": {"search_path": PRIVATE_SCHEMA}}
        if remote:
            connect_args["ssl"] = "require"
        return urlunsplit(parts._replace(query=urlencode(query))), connect_args

    if scheme.startswith("sqlite"):
        return "sqlite+aiosqlite://" + rest, {}

    raise ValueError("Unsupported database URL for Iyobo's memory; use a PostgreSQL or SQLite URL.")


def create_engine_for(database_url: str) -> AsyncEngine:
    """An async engine for Iyobo's memory database.

    SQLite connections aren't pooled: an aiosqlite connection belongs to the event loop that
    opened it, and tests and single-process servers can run more than one loop.
    """
    async_url, connect_args = async_database_url(database_url)
    options: dict[str, Any] = {"connect_args": connect_args, "pool_pre_ping": True}
    if async_url.startswith("sqlite"):
        options["poolclass"] = NullPool
    return create_async_engine(async_url, **options)


def _clip(value: Optional[str], field: str) -> Optional[str]:
    if value is None:
        return None
    value = " ".join(str(value).split())
    return value[: MAX_FIELD_CHARS[field]] or None


class LearningStore:
    """Async access to the knowledge review queue."""

    def __init__(self, database_url: str, user_id_salt: str, max_per_day: int = 10):
        self.engine: AsyncEngine = create_engine_for(database_url)
        self._salt = user_id_salt.encode("utf-8")
        self.max_per_day = max_per_day
        self._schema_ready = False

    async def ensure_schema(self) -> None:
        """Create the table if it doesn't exist yet (the Supabase migration is still recommended)."""
        if self._schema_ready:
            return
        async with self.engine.begin() as conn:
            if conn.dialect.name == "postgresql":
                await conn.execute(sa.text(f"create schema if not exists {PRIVATE_SCHEMA}"))
            await conn.run_sync(metadata.create_all, checkfirst=True)
        self._schema_ready = True

    def user_ref(self, user_id: Optional[str]) -> Optional[str]:
        """A salted one-way hash of the user id, so suggestions can be grouped without storing who sent them."""
        if not user_id:
            return None
        return hmac.new(self._salt, str(user_id).encode("utf-8"), hashlib.sha256).hexdigest()[:32]

    async def suggestions_today(self, user_id: Optional[str]) -> int:
        await self.ensure_schema()
        ref = self.user_ref(user_id)
        if ref is None:
            return 0
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        async with self.engine.connect() as conn:
            result = await conn.execute(
                sa.select(sa.func.count()).select_from(suggestions)
                .where(suggestions.c.user_ref == ref, suggestions.c.created_at >= since)
            )
            return int(result.scalar_one())

    async def suggest(
        self,
        *,
        note: str,
        edo: Optional[str] = None,
        english: Optional[str] = None,
        category: Optional[str] = None,
        example: Optional[str] = None,
        source_channel: str = "web",
        user_id: Optional[str] = None,
    ) -> Optional[int]:
        """Queue a suggestion for review. Returns its id, or None when this user hit today's limit."""
        await self.ensure_schema()
        clean_note = _clip(note, "note")
        if not clean_note:
            raise ValueError("A suggestion needs a note describing what to learn.")
        if await self.suggestions_today(user_id) >= self.max_per_day:
            return None
        row = {
            "edo": _clip(edo, "edo"),
            "english": _clip(english, "english"),
            "category": _clip(category, "category"),
            "example": _clip(example, "example"),
            "note": clean_note,
            "source_channel": source_channel if source_channel in SOURCE_CHANNELS else "web",
            "user_ref": self.user_ref(user_id),
            "status": "pending",
        }
        async with self.engine.begin() as conn:
            result = await conn.execute(suggestions.insert().values(**row).returning(suggestions.c.id))
            return int(result.scalar_one())

    async def list(self, status: str = "pending", limit: int = 50) -> list[dict[str, Any]]:
        await self.ensure_schema()
        if status not in STATUSES:
            raise ValueError(f"status must be one of {', '.join(STATUSES)}")
        async with self.engine.connect() as conn:
            result = await conn.execute(
                sa.select(suggestions).where(suggestions.c.status == status)
                .order_by(suggestions.c.created_at.desc()).limit(max(1, min(limit, 200)))
            )
            return [dict(row._mapping) for row in result]

    async def review(self, suggestion_id: int, approve: bool, reviewer_note: Optional[str] = None) -> Optional[dict[str, Any]]:
        """Approve or reject a pending suggestion. Returns the updated row, or None if it wasn't pending."""
        await self.ensure_schema()
        now = datetime.now(timezone.utc)
        async with self.engine.begin() as conn:
            result = await conn.execute(
                suggestions.update()
                .where(suggestions.c.id == suggestion_id, suggestions.c.status == "pending")
                .values(
                    status="approved" if approve else "rejected",
                    reviewer_note=_clip(reviewer_note, "note"),
                    reviewed_at=now,
                    updated_at=now,
                )
                .returning(*suggestions.c)
            )
            row = result.first()
            return dict(row._mapping) if row else None

    async def approved(self) -> list[dict[str, Any]]:
        return await self.list(status="approved", limit=200)

    async def close(self) -> None:
        await self.engine.dispose()
