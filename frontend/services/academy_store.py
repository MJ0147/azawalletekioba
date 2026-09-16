"""
Grades, points and IDIA Coin conversion requests for the Edo Language Academy.

Kept in PostgreSQL (the site's Supabase database: ACADEMY_DATABASE_URL, else DATABASE_URL) in a
private "academy" schema that Supabase's public REST API doesn't expose, or in SQLite for local
development and tests. Tables are created on first use.

Points are a ledger: exams add points, a conversion request takes them out, and a rejected request
puts them back. A learner's balance is the sum of their ledger entries.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

SCHEMA = "academy"
metadata = sa.MetaData(schema=SCHEMA)

exam_attempts = sa.Table(
    "exam_attempts",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("wallet", sa.String(80), nullable=False, index=True),
    sa.Column("grade", sa.Integer, nullable=False),
    sa.Column("status", sa.String(16), nullable=False),  # in_progress, passed, failed
    sa.Column("questions", sa.Text, nullable=False),  # JSON, including the answers: never sent to the browser
    sa.Column("responses", sa.Text, nullable=False),  # JSON list of {"choice", "correct"}
    sa.Column("current", sa.Integer, nullable=False),  # index of the next question to answer
    sa.Column("correct", sa.Integer, nullable=False),
    sa.Column("total", sa.Integer, nullable=False),
    sa.Column("points_awarded", sa.Integer, nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("finished_at", sa.DateTime(timezone=True)),
)

grade_records = sa.Table(
    "grade_records",
    metadata,
    sa.Column("wallet", sa.String(80), primary_key=True),
    sa.Column("grade", sa.Integer, primary_key=True),
    sa.Column("best_correct", sa.Integer, nullable=False),
    sa.Column("total", sa.Integer, nullable=False),
    sa.Column("attempts", sa.Integer, nullable=False),
    sa.Column("passed_at", sa.DateTime(timezone=True)),
)

points_ledger = sa.Table(
    "points_ledger",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("wallet", sa.String(80), nullable=False, index=True),
    sa.Column("delta", sa.Integer, nullable=False),
    sa.Column("reason", sa.String(32), nullable=False),  # exam, conversion, conversion_refund
    sa.Column("ref", sa.String(64)),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

conversion_requests = sa.Table(
    "conversion_requests",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("wallet", sa.String(80), nullable=False, index=True),
    sa.Column("points", sa.Integer, nullable=False),
    sa.Column("idia_amount", sa.Numeric(18, 9), nullable=False),
    sa.Column("status", sa.String(16), nullable=False),  # pending, paid, rejected
    sa.Column("tx_hash", sa.String(128)),
    sa.Column("reviewer_note", sa.String(1000)),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("reviewed_at", sa.DateTime(timezone=True)),
)

# At most one request per wallet waits for review at a time.
sa.Index(
    "one_pending_conversion_per_wallet",
    conversion_requests.c.wallet,
    unique=True,
    postgresql_where=conversion_requests.c.status == "pending",
    sqlite_where=conversion_requests.c.status == "pending",
)


class ConversionPending(Exception):
    """This wallet already has a conversion request waiting for review."""


class NotEnoughPoints(Exception):
    """The wallet's balance is below one IDIA's worth of points."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _plain(row: Any) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key, value in dict(row).items():
        if isinstance(value, datetime):
            values[key] = value.isoformat()
        elif isinstance(value, Decimal):
            values[key] = f"{value.normalize():f}"
        else:
            values[key] = value
    return values


def _attempt(row: Any) -> dict[str, Any]:
    attempt = _plain(row)
    attempt["questions"] = json.loads(attempt["questions"])
    attempt["responses"] = json.loads(attempt["responses"])
    return attempt


def async_database_url(url: str) -> tuple[str, dict[str, Any]]:
    """Turn a PostgreSQL or SQLite URL into an async SQLAlchemy URL and its driver connect arguments."""
    raw = url.strip()
    parts = urlsplit(raw)
    scheme = parts.scheme.lower()
    if scheme.startswith("sqlite"):
        return "sqlite+aiosqlite" + raw[len(parts.scheme):], {}
    if scheme in {"postgres", "postgresql"} or scheme.startswith("postgresql+"):
        query = urlencode([(key, value) for key, value in parse_qsl(parts.query) if key.lower() != "sslmode"])
        # Supabase's pooler shares server connections between clients, so prepared statements can't be cached.
        connect_args: dict[str, Any] = {"statement_cache_size": 0}
        if (parts.hostname or "").lower() not in {"", "localhost", "127.0.0.1"}:
            connect_args["ssl"] = "require"
        return urlunsplit(("postgresql+asyncpg", parts.netloc, parts.path, query, "")), connect_args
    raise ValueError("The Academy database must be a PostgreSQL or SQLite URL.")


class AcademyStore:
    def __init__(self, database_url: str):
        url, connect_args = async_database_url(database_url)
        self.is_sqlite = url.startswith("sqlite")
        options = {"schema_translate_map": {SCHEMA: None}} if self.is_sqlite else {}
        # NullPool: serverless instances freeze between requests, so pooled connections would go stale.
        self.engine = create_async_engine(url, poolclass=NullPool, connect_args=connect_args, execution_options=options)
        self._schema_ready = False

    async def ensure_schema(self) -> None:
        if self._schema_ready:
            return
        async with self.engine.begin() as conn:
            if not self.is_sqlite:
                await conn.execute(sa.text(f'create schema if not exists "{SCHEMA}"'))
            await conn.run_sync(metadata.create_all, checkfirst=True)
        self._schema_ready = True

    # ── Exams ────────────────────────────────────────────────────────────────

    async def get_attempt(self, attempt_id: str) -> Optional[dict[str, Any]]:
        await self.ensure_schema()
        async with self.engine.connect() as conn:
            row = (await conn.execute(sa.select(exam_attempts).where(exam_attempts.c.id == attempt_id))).mappings().first()
        return _attempt(row) if row else None

    async def open_attempt(self, wallet: str, grade: int) -> Optional[dict[str, Any]]:
        await self.ensure_schema()
        query = (
            sa.select(exam_attempts)
            .where(exam_attempts.c.wallet == wallet, exam_attempts.c.grade == grade, exam_attempts.c.status == "in_progress")
            .order_by(exam_attempts.c.started_at.desc())
            .limit(1)
        )
        async with self.engine.connect() as conn:
            row = (await conn.execute(query)).mappings().first()
        return _attempt(row) if row else None

    async def open_attempts(self, wallet: str) -> dict[int, dict[str, int]]:
        """Unfinished exams by grade: how many questions are answered out of how many."""
        await self.ensure_schema()
        query = sa.select(exam_attempts.c.grade, exam_attempts.c.current, exam_attempts.c.total).where(
            exam_attempts.c.wallet == wallet, exam_attempts.c.status == "in_progress"
        )
        async with self.engine.connect() as conn:
            rows = (await conn.execute(query)).mappings().all()
        return {row["grade"]: {"answered": row["current"], "total": row["total"]} for row in rows}

    async def create_attempt(self, wallet: str, grade: int, questions: list[dict[str, Any]]) -> dict[str, Any]:
        await self.ensure_schema()
        attempt_id = uuid.uuid4().hex
        record_key = (grade_records.c.wallet == wallet) & (grade_records.c.grade == grade)
        async with self.engine.begin() as conn:
            record = (await conn.execute(sa.select(grade_records.c.grade).where(record_key))).first()
            if record is None:
                await conn.execute(
                    grade_records.insert().values(wallet=wallet, grade=grade, best_correct=0, total=len(questions), attempts=1)
                )
            else:
                await conn.execute(grade_records.update().where(record_key).values(attempts=grade_records.c.attempts + 1))
            await conn.execute(
                exam_attempts.insert().values(
                    id=attempt_id,
                    wallet=wallet,
                    grade=grade,
                    status="in_progress",
                    questions=json.dumps(questions, ensure_ascii=False),
                    responses="[]",
                    current=0,
                    correct=0,
                    total=len(questions),
                    points_awarded=0,
                    started_at=_now(),
                )
            )
        attempt = await self.get_attempt(attempt_id)
        assert attempt is not None
        return attempt

    async def record_answer(
        self, attempt_id: str, index: int, response: dict[str, Any], correct: bool
    ) -> Optional[dict[str, Any]]:
        """Save the answer to question `index`. Returns the updated exam, or None if that question was
        already answered (or the exam is closed), so each question counts once."""
        attempt = await self.get_attempt(attempt_id)
        if attempt is None or attempt["status"] != "in_progress" or attempt["current"] != index:
            return None
        async with self.engine.begin() as conn:
            result = await conn.execute(
                exam_attempts.update()
                .where(
                    exam_attempts.c.id == attempt_id,
                    exam_attempts.c.status == "in_progress",
                    exam_attempts.c.current == index,
                )
                .values(
                    current=index + 1,
                    correct=exam_attempts.c.correct + (1 if correct else 0),
                    responses=json.dumps(attempt["responses"] + [response]),
                )
            )
        if result.rowcount != 1:
            return None
        return await self.get_attempt(attempt_id)

    async def finish_attempt(self, attempt_id: str, *, pass_percent: int, points_per_correct: int) -> dict[str, Any]:
        """Close a fully answered exam: pass or fail it, award points only for beating the best score in
        that grade, and keep the best score."""
        await self.ensure_schema()
        async with self.engine.begin() as conn:
            attempt = (
                await conn.execute(
                    sa.select(exam_attempts)
                    .where(
                        exam_attempts.c.id == attempt_id,
                        exam_attempts.c.status == "in_progress",
                        exam_attempts.c.current >= exam_attempts.c.total,
                    )
                    .with_for_update()
                )
            ).mappings().first()
            if attempt is not None:
                record_key = (grade_records.c.wallet == attempt["wallet"]) & (grade_records.c.grade == attempt["grade"])
                record = (await conn.execute(sa.select(grade_records).where(record_key).with_for_update())).mappings().first()
                best = record["best_correct"] if record else 0
                points = max(0, attempt["correct"] - best) * points_per_correct
                passed = attempt["correct"] * 100 >= pass_percent * attempt["total"]
                now = _now()
                await conn.execute(
                    exam_attempts.update()
                    .where(exam_attempts.c.id == attempt_id)
                    .values(status="passed" if passed else "failed", points_awarded=points, finished_at=now)
                )
                values: dict[str, Any] = {"best_correct": max(best, attempt["correct"]), "total": attempt["total"]}
                if passed and not (record and record["passed_at"]):
                    values["passed_at"] = now
                await conn.execute(grade_records.update().where(record_key).values(**values))
                if points:
                    await conn.execute(
                        points_ledger.insert().values(
                            wallet=attempt["wallet"], delta=points, reason="exam", ref=attempt_id, created_at=now
                        )
                    )
        finished = await self.get_attempt(attempt_id)
        assert finished is not None
        return finished

    async def grade_records(self, wallet: str) -> dict[int, dict[str, Any]]:
        await self.ensure_schema()
        async with self.engine.connect() as conn:
            rows = (await conn.execute(sa.select(grade_records).where(grade_records.c.wallet == wallet))).mappings().all()
        return {row["grade"]: _plain(row) for row in rows}

    # ── Points and conversions ───────────────────────────────────────────────

    async def points(self, wallet: str) -> dict[str, int]:
        await self.ensure_schema()
        total = sa.func.coalesce(sa.func.sum(points_ledger.c.delta), 0)
        async with self.engine.connect() as conn:
            available = (await conn.execute(sa.select(total).where(points_ledger.c.wallet == wallet))).scalar_one()
            earned = (
                await conn.execute(sa.select(total).where(points_ledger.c.wallet == wallet, points_ledger.c.reason == "exam"))
            ).scalar_one()
        return {"available": int(available), "earned": int(earned)}

    async def create_conversion(self, wallet: str, points_per_idia: int) -> dict[str, Any]:
        """Convert every whole IDIA's worth of the wallet's points into a request awaiting review."""
        await self.ensure_schema()
        try:
            async with self.engine.begin() as conn:
                pending = (
                    await conn.execute(
                        sa.select(conversion_requests.c.id).where(
                            conversion_requests.c.wallet == wallet, conversion_requests.c.status == "pending"
                        )
                    )
                ).first()
                if pending is not None:
                    raise ConversionPending()
                balance = int(
                    (
                        await conn.execute(
                            sa.select(sa.func.coalesce(sa.func.sum(points_ledger.c.delta), 0)).where(
                                points_ledger.c.wallet == wallet
                            )
                        )
                    ).scalar_one()
                )
                points = (balance // points_per_idia) * points_per_idia
                if points <= 0:
                    raise NotEnoughPoints()
                now = _now()
                result = await conn.execute(
                    conversion_requests.insert().values(
                        wallet=wallet,
                        points=points,
                        idia_amount=Decimal(points) / Decimal(points_per_idia),
                        status="pending",
                        created_at=now,
                    )
                )
                conversion_id = result.inserted_primary_key[0]
                await conn.execute(
                    points_ledger.insert().values(
                        wallet=wallet, delta=-points, reason="conversion", ref=str(conversion_id), created_at=now
                    )
                )
        except IntegrityError as exc:  # a second request raced this one past the pending check
            raise ConversionPending() from exc
        conversion = await self.get_conversion(conversion_id)
        assert conversion is not None
        return conversion

    async def get_conversion(self, conversion_id: int) -> Optional[dict[str, Any]]:
        await self.ensure_schema()
        async with self.engine.connect() as conn:
            row = (
                await conn.execute(sa.select(conversion_requests).where(conversion_requests.c.id == conversion_id))
            ).mappings().first()
        return _plain(row) if row else None

    async def list_conversions(self, status: str, limit: int) -> list[dict[str, Any]]:
        await self.ensure_schema()
        query = sa.select(conversion_requests).order_by(conversion_requests.c.created_at.desc()).limit(limit)
        if status != "all":
            query = query.where(conversion_requests.c.status == status)
        async with self.engine.connect() as conn:
            rows = (await conn.execute(query)).mappings().all()
        return [_plain(row) for row in rows]

    async def conversions_for(self, wallet: str, limit: int = 10) -> list[dict[str, Any]]:
        await self.ensure_schema()
        query = (
            sa.select(conversion_requests)
            .where(conversion_requests.c.wallet == wallet)
            .order_by(conversion_requests.c.created_at.desc())
            .limit(limit)
        )
        async with self.engine.connect() as conn:
            rows = (await conn.execute(query)).mappings().all()
        return [_plain(row) for row in rows]

    async def review_conversion(
        self, conversion_id: int, *, paid: bool, tx_hash: Optional[str], note: Optional[str]
    ) -> Optional[dict[str, Any]]:
        """Mark a pending request paid (with the IDIA transfer's hash) or reject it, refunding its points.
        Returns None if there's no pending request with that id."""
        await self.ensure_schema()
        async with self.engine.begin() as conn:
            row = (
                await conn.execute(
                    sa.select(conversion_requests)
                    .where(conversion_requests.c.id == conversion_id, conversion_requests.c.status == "pending")
                    .with_for_update()
                )
            ).mappings().first()
            if row is None:
                return None
            now = _now()
            await conn.execute(
                conversion_requests.update()
                .where(conversion_requests.c.id == conversion_id)
                .values(status="paid" if paid else "rejected", tx_hash=tx_hash, reviewer_note=note, reviewed_at=now)
            )
            if not paid:
                await conn.execute(
                    points_ledger.insert().values(
                        wallet=row["wallet"], delta=row["points"], reason="conversion_refund", ref=str(conversion_id), created_at=now
                    )
                )
        return await self.get_conversion(conversion_id)
