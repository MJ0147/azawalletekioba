"""
Flutterwave FX service — live USDT/NGN rate for IDIA pricing.

DeDust prices IDIA in USD (IDIA -> TON -> USD), but the final USD -> NGN leg
has no on-chain source. Flutterwave's transfer-rates endpoint supplies it.

Flutterwave quotes fiat only — there is no USDT currency code — so the USD
rate is used as the USDT rate. USDT is a USD-pegged stablecoin, so this is
the intended proxy; set FLW_FX_SOURCE_CURRENCY to override.

Requires FLW_SECRET_KEY. Without it (or if the call fails) every function
returns None and the caller falls back to the static USDT_NGN_RATE.
"""
from __future__ import annotations

import os
import time
from typing import Any, Optional

import httpx

FLW_API_BASE = os.getenv("FLW_API_BASE", "https://api.flutterwave.com/v3").rstrip("/")
FLW_SECRET_KEY = os.getenv("FLW_SECRET_KEY", "").strip()

# Flutterwave has no USDT currency code; USDT is USD-pegged, so USD is the proxy.
FLW_FX_SOURCE_CURRENCY = os.getenv("FLW_FX_SOURCE_CURRENCY", "USD").upper()
FLW_FX_DESTINATION_CURRENCY = os.getenv("FLW_FX_DESTINATION_CURRENCY", "NGN").upper()

# FX moves slowly and the endpoint is rate limited, so cache generously.
FLW_CACHE_TTL = int(os.getenv("FLW_CACHE_TTL", "300"))

# Guard rails: a rate outside this band is almost certainly a bad response
# (wrong direction, wrong currency) and must not reach a customer's checkout.
FLW_RATE_MIN = float(os.getenv("FLW_RATE_MIN", "100"))
FLW_RATE_MAX = float(os.getenv("FLW_RATE_MAX", "100000"))

_CACHE: dict[str, Any] = {}


def is_configured() -> bool:
    """True when a Flutterwave secret key is present."""
    return bool(FLW_SECRET_KEY)


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {FLW_SECRET_KEY}",
        "Accept": "application/json",
    }


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _extract_rate(data: dict[str, Any]) -> float:
    """
    Pull NGN-per-source-unit out of a transfers/rates payload.

    Prefer destination.amount / source.amount over the bare `rate` field:
    Flutterwave interprets `amount` against one side of the pair depending on
    the account, and the explicit amounts are unambiguous.
    """
    source = data.get("source") or {}
    destination = data.get("destination") or {}

    source_amount = _safe_float(source.get("amount"))
    destination_amount = _safe_float(destination.get("amount"))

    # Only trust the pair when the currencies are the ones we asked for.
    currencies_match = (
        str(source.get("currency", "")).upper() == FLW_FX_SOURCE_CURRENCY
        and str(destination.get("currency", "")).upper() == FLW_FX_DESTINATION_CURRENCY
    )
    if currencies_match and source_amount > 0 and destination_amount > 0:
        return destination_amount / source_amount

    return _safe_float(data.get("rate"))


async def fetch_usdt_ngn_rate() -> Optional[float]:
    """
    NGN per 1 USDT from Flutterwave (cached), or None when unavailable.

    None means "use your fallback" — a missing key, a failed call, or a rate
    outside the sanity band all land here.
    """
    if not is_configured():
        return None

    now = time.time()
    if _CACHE.get("ts", 0) + FLW_CACHE_TTL > now:
        cached = _CACHE.get("rate")
        if cached:
            return float(cached)

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                f"{FLW_API_BASE}/transfers/rates",
                params={
                    "amount": 1,
                    "source_currency": FLW_FX_SOURCE_CURRENCY,
                    "destination_currency": FLW_FX_DESTINATION_CURRENCY,
                },
                headers=_headers(),
            )
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return None

    if str(payload.get("status", "")).lower() != "success":
        return None

    rate = _extract_rate(payload.get("data") or {})
    if not (FLW_RATE_MIN <= rate <= FLW_RATE_MAX):
        # Implausible quote — better to fall back than to misprice a basket.
        return None

    _CACHE["rate"] = rate
    _CACHE["ts"] = now
    return rate


async def get_fx_snapshot() -> dict[str, Any]:
    """Diagnostic view of the Flutterwave FX leg."""
    rate = await fetch_usdt_ngn_rate()
    return {
        "source": "flutterwave",
        "configured": is_configured(),
        "pair": f"{FLW_FX_SOURCE_CURRENCY}/{FLW_FX_DESTINATION_CURRENCY}",
        "ngn_per_usdt": rate,
        "live": rate is not None,
        "cache_ttl_seconds": FLW_CACHE_TTL,
    }
