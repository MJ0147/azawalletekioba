"""
Supabase service — async Postgres/PostgREST access for the EKIOBA frontend.

EKIOBA is a Python stack, so this uses `supabase-py`'s **async** client
(`acreate_client`). The synchronous client would block FastAPI's event loop on
every query.

Two keys, two very different trust levels:

  * SUPABASE_KEY  — the publishable ("anon") key. Safe to expose, but every
    query is subject to Row Level Security. Use this by default.
  * SUPABASE_SERVICE_KEY — the secret/service-role key. **Bypasses RLS
    entirely.** Server-side only; never render it into a template, log it, or
    ship it to a browser. Opt in per call with `service=True`.

If the package or the configuration is missing, `is_configured()` returns False
and every call raises `SupabaseError` with a clear message, so a missing
Supabase never takes the site down.
"""
from __future__ import annotations

import os
from typing import Any, Optional

try:
    from supabase import AsyncClient, acreate_client

    SUPABASE_SDK_AVAILABLE = True
except Exception:  # pragma: no cover - only on a broken install
    AsyncClient = None  # type: ignore[assignment]
    acreate_client = None  # type: ignore[assignment]

    SUPABASE_SDK_AVAILABLE = False


class SupabaseError(RuntimeError):
    """Raised when Supabase is unavailable or misconfigured."""


def _env(*names: str, default: str = "") -> str:
    """First non-empty value among `names`."""
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


# NEXT_PUBLIC_* names are accepted so a .env copied from Supabase's own
# Next.js quickstart still works here.
SUPABASE_URL = _env("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL").rstrip("/")
SUPABASE_KEY = _env(
    "SUPABASE_KEY",
    "SUPABASE_PUBLISHABLE_KEY",
    "SUPABASE_ANON_KEY",
    "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY",
)
SUPABASE_SERVICE_KEY = _env(
    "SUPABASE_SERVICE_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    # Supabase's newer dashboard calls this the "secret" key.
    "SUPABASE_SECRET_KEY",
)

_clients: dict[bool, Any] = {}


def is_configured(service: bool = False) -> bool:
    """True when the SDK is installed and a URL + suitable key are present."""
    if not SUPABASE_SDK_AVAILABLE or not SUPABASE_URL:
        return False
    return bool(SUPABASE_SERVICE_KEY if service else SUPABASE_KEY)


def _key_for(service: bool) -> str:
    if service:
        if not SUPABASE_SERVICE_KEY:
            raise SupabaseError(
                "SUPABASE_SERVICE_KEY is not configured; cannot run a "
                "service-role query."
            )
        return SUPABASE_SERVICE_KEY
    if not SUPABASE_KEY:
        raise SupabaseError("SUPABASE_KEY is not configured.")
    return SUPABASE_KEY


async def get_client(service: bool = False) -> "AsyncClient":
    """
    Return a cached async Supabase client.

    `service=True` uses the service-role key and therefore bypasses RLS —
    only for trusted server-side work.
    """
    if not SUPABASE_SDK_AVAILABLE:
        raise SupabaseError(
            "supabase-py is not installed; Supabase features are unavailable. "
            "Install it with 'pip install supabase'."
        )
    if not SUPABASE_URL:
        raise SupabaseError(
            "SUPABASE_URL is not configured. Set it to your project URL, "
            "e.g. https://<project-ref>.supabase.co"
        )

    if service not in _clients:
        _clients[service] = await acreate_client(SUPABASE_URL, _key_for(service))
    return _clients[service]


async def select(
    table: str,
    columns: str = "*",
    limit: Optional[int] = None,
    order: Optional[str] = None,
    descending: bool = False,
    filters: Optional[dict[str, Any]] = None,
    service: bool = False,
) -> list[dict[str, Any]]:
    """
    Read rows from a table. Returns [] rather than raising when the table is
    simply empty; genuine failures raise SupabaseError.
    """
    client = await get_client(service=service)
    query = client.table(table).select(columns)

    for column, value in (filters or {}).items():
        query = query.eq(column, value)
    if order:
        query = query.order(order, desc=descending)
    if limit:
        query = query.limit(limit)

    try:
        response = await query.execute()
    except Exception as exc:
        raise SupabaseError(f"Supabase query on '{table}' failed: {exc}") from exc

    return list(response.data or [])


async def insert(
    table: str,
    rows: dict[str, Any] | list[dict[str, Any]],
    service: bool = False,
) -> list[dict[str, Any]]:
    """Insert one row or many. Writes usually need `service=True` under RLS."""
    client = await get_client(service=service)
    try:
        response = await client.table(table).insert(rows).execute()
    except Exception as exc:
        raise SupabaseError(f"Supabase insert into '{table}' failed: {exc}") from exc
    return list(response.data or [])


async def health_check(probe_table: Optional[str] = None) -> dict[str, Any]:
    """
    Diagnostic snapshot: is Supabase installed, configured and reachable, and
    is `probe_table` visible to the key in use.
    """
    status: dict[str, Any] = {
        "sdk_installed": SUPABASE_SDK_AVAILABLE,
        "configured": is_configured(),
        "url": SUPABASE_URL or None,
        "publishable_key": bool(SUPABASE_KEY),
        "service_key": bool(SUPABASE_SERVICE_KEY),
        "reachable": False,
        "probe_table": probe_table,
        "table_readable": None,
        "error": None,
    }

    if not status["configured"]:
        status["error"] = "Supabase is not configured."
        return status

    table = probe_table or os.getenv("SUPABASE_HEALTH_TABLE", "").strip()
    if not table:
        # Nothing to probe: report configuration only, without guessing a name.
        status["reachable"] = True
        status["error"] = "No probe table configured (set SUPABASE_HEALTH_TABLE)."
        return status

    try:
        await select(table, columns="*", limit=1)
        status["reachable"] = True
        status["table_readable"] = True
    except SupabaseError as exc:
        message = str(exc)
        # A missing table still proves we reached PostgREST and authenticated.
        if "PGRST205" in message or "Could not find the table" in message:
            status["reachable"] = True
            status["table_readable"] = False
            status["error"] = f"Table '{table}' does not exist in this project."
        else:
            status["error"] = message

    return status
