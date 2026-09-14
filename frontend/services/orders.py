"""
Order persistence — records IDIA checkout intent in Supabase.

Design rule: **recording an order must never break a checkout.** A shopper's
payment does not depend on our bookkeeping, so every function here is
best-effort: it returns False and logs on failure rather than raising. If
Supabase is down, misconfigured, or the table does not exist yet, checkout
carries on exactly as before.

Writes use the service-role key. The `orders` table has RLS enabled with no
anon policy (see Knowledge Base/Supabase/001_orders_table.sql), so the
publishable key cannot read or write it — which is the point: order data
should never be reachable from a browser. Routes that expose it must check
`is_admin()` first, because the service key bypasses RLS.
"""
from __future__ import annotations

import hmac
import logging
import os
from typing import Any, Optional

from services import supabase_client

logger = logging.getLogger("ekioba.orders")

ORDERS_TABLE = os.getenv("SUPABASE_ORDERS_TABLE", "orders")

# Bearer token for the admin order endpoints. Unset means those endpoints are
# closed to everyone, which is the safe default.
ORDERS_ADMIN_TOKEN = os.getenv("ORDERS_ADMIN_TOKEN", "").strip()

# Mirrors the CHECK constraint on the table.
VALID_STATUSES = {"pending", "submitted", "confirmed", "failed", "expired"}

# A missing table is a one-time setup problem, not a per-request error. Log it
# once and stay quiet afterwards so the logs are not flooded.
_missing_table_warned = False


def is_enabled() -> bool:
    """Order recording needs the service-role key; without it, stay disabled."""
    return supabase_client.is_configured(service=True)


def is_admin(authorization: Optional[str]) -> bool:
    """
    True when `authorization` is `Bearer <ORDERS_ADMIN_TOKEN>`.

    Always False when no token is configured.
    """
    if not ORDERS_ADMIN_TOKEN or not authorization:
        return False
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return False
    return hmac.compare_digest(
        token.strip().encode("utf-8"), ORDERS_ADMIN_TOKEN.encode("utf-8")
    )


def _is_missing_table(message: str) -> bool:
    return "PGRST205" in message or "Could not find the table" in message


def _warn_missing_table_once() -> None:
    global _missing_table_warned
    if not _missing_table_warned:
        _missing_table_warned = True
        logger.warning(
            "Supabase table '%s' does not exist; order recording is disabled. "
            "Run Knowledge Base/Supabase/001_orders_table.sql to enable it.",
            ORDERS_TABLE,
        )


def build_row(payment: dict[str, Any], status: str = "pending") -> dict[str, Any]:
    """Map a TON payment request onto an `orders` row."""
    tx = payment.get("ton_connect_tx") or {}
    messages = tx.get("messages") or [{}]
    return {
        "order_id": payment.get("order_id"),
        "product_name": payment.get("product"),
        "amount_ngn": payment.get("amount_ngn"),
        "amount_idia": payment.get("amount_idia"),
        "chain": payment.get("chain", "ton"),
        "sender_address": payment.get("sender"),
        "jetton_wallet": payment.get("sender_jetton_wallet") or messages[0].get("address"),
        "status": status if status in VALID_STATUSES else "pending",
        "is_cart_checkout": bool(payment.get("is_cart_checkout")),
        "cart_items": payment.get("cart_items") or [],
    }


async def record(payment: dict[str, Any], status: str = "pending") -> bool:
    """
    Persist a payment request. Returns True when stored.

    A plain insert, never an upsert: order ids are minted server-side, so an
    existing row must never be overwritten by a later request.
    """
    if not is_enabled():
        return False

    row = build_row(payment, status)
    if not row.get("order_id"):
        logger.warning("Refusing to record an order with no order_id.")
        return False

    try:
        client = await supabase_client.get_client(service=True)
        await client.table(ORDERS_TABLE).insert(row).execute()
    except Exception as exc:  # never propagate into the checkout path
        message = str(exc)
        if _is_missing_table(message):
            _warn_missing_table_once()
        else:
            logger.warning("Could not record order %s: %s", row["order_id"], message)
        return False

    return True


async def set_status(
    order_id: str,
    status: str,
    tx_hash: Optional[str] = None,
) -> bool:
    """Advance an order's status (e.g. pending -> submitted -> confirmed)."""
    if not is_enabled() or not order_id:
        return False
    if status not in VALID_STATUSES:
        logger.warning("Refusing to set unknown order status %r.", status)
        return False

    patch: dict[str, Any] = {"status": status}
    if tx_hash:
        patch["tx_hash"] = tx_hash

    try:
        client = await supabase_client.get_client(service=True)
        await client.table(ORDERS_TABLE).update(patch).eq("order_id", order_id).execute()
    except Exception as exc:
        message = str(exc)
        if _is_missing_table(message):
            _warn_missing_table_once()
        else:
            logger.warning("Could not update order %s: %s", order_id, message)
        return False

    return True


async def recent(limit: int = 20) -> list[dict[str, Any]]:
    """Most recent orders, newest first. Returns [] when unavailable."""
    if not is_enabled():
        return []
    try:
        return await supabase_client.select(
            ORDERS_TABLE,
            limit=max(1, min(limit, 100)),
            order="created_at",
            descending=True,
            service=True,
        )
    except supabase_client.SupabaseError as exc:
        if _is_missing_table(str(exc)):
            _warn_missing_table_once()
        else:
            logger.warning("Could not list orders: %s", exc)
        return []


async def get(order_id: str) -> Optional[dict[str, Any]]:
    """Fetch a single order by its EKIOBA reference."""
    if not is_enabled() or not order_id:
        return None
    try:
        rows = await supabase_client.select(
            ORDERS_TABLE, filters={"order_id": order_id}, limit=1, service=True
        )
    except supabase_client.SupabaseError as exc:
        if _is_missing_table(str(exc)):
            _warn_missing_table_once()
        else:
            logger.warning("Could not fetch order %s: %s", order_id, exc)
        return None
    return rows[0] if rows else None
