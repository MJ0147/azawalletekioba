"""
Idia Coin token service — price fetching and NGN conversion.
Idia Coin is the native payment token on the TON blockchain for EKIOBA.

Price sources, in priority order:
  1. DeDust — live on-chain pool reserves (IDIA -> TON -> USD). Authoritative
     while a TON/IDIA pool exists.
  2. CoinGecko — only useful once IDIA is listed there.
  3. The IDIA_NGN_RATE / IDIA_USD_RATE environment fallback.

The final USD -> NGN leg is a separate concern with its own chain:
  1. Flutterwave live FX
  2. CoinGecko tether->NGN
  3. The static USDT_NGN_RATE

`get_last_rate_source()` and `get_last_fx_source()` report which of each
produced the current rate, so the UI and operators can tell a real market
price from the placeholder.
"""
from __future__ import annotations

import os
import time
from typing import Any, Optional

import httpx

from services import dedust, flutterwave

# On-chain token identifier (configure via env). The IDIA Jetton master on
# TON mainnet; TON_CONTRACT_ADDRESS is accepted as a legacy alias.
IDIA_TON_JETTON_ADDRESS = os.getenv(
    "IDIA_TON_JETTON_ADDRESS",
    os.getenv("TON_CONTRACT_ADDRESS", "EQC8QIjU-uXwrlj9B9Zc0ZBIaTS5TLzFb6djJIRwyLa6Enqs"),
)
IDIA_TON_DECIMALS = int(os.getenv("IDIA_TON_DECIMALS", "9"))

# Default fallback rate: 1 IDIA = 0.02 USD ~ 30 NGN
_DEFAULT_NGN_PER_IDIA = float(os.getenv("IDIA_NGN_RATE", "30.0"))
_DEFAULT_USD_PER_IDIA = float(os.getenv("IDIA_USD_RATE", "0.02"))
# An explicitly configured NGN rate is an operator override and wins outright;
# otherwise the USD placeholder is converted with the live FX rate.
_NGN_RATE_PINNED = bool(os.getenv("IDIA_NGN_RATE"))

_CACHE: dict[str, Any] = {}
_CACHE_TTL = 120  # seconds

SOURCE_DEDUST = "dedust"
SOURCE_COINGECKO = "coingecko"
SOURCE_FALLBACK = "fallback"
SOURCE_FLUTTERWAVE = "flutterwave"
SOURCE_STATIC = "static"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_last_rate_source() -> str:
    """Which source produced the most recently computed IDIA price."""
    return str(_CACHE.get("source") or SOURCE_FALLBACK)


def get_last_fx_source() -> str:
    """Which source produced the most recently used USDT/NGN rate."""
    return str(_CACHE.get("fx_source") or SOURCE_STATIC)


def _static_usdt_ngn_rate() -> float:
    return _safe_float(os.getenv("USDT_NGN_RATE", "1500.0"), 1500.0)


async def resolve_usdt_ngn_rate(coingecko: Optional[dict[str, float]] = None) -> float:
    """
    NGN per 1 USDT: Flutterwave live FX, else CoinGecko tether->NGN,
    else the static USDT_NGN_RATE. Records which one was used.
    """
    try:
        live = await flutterwave.fetch_usdt_ngn_rate()
    except Exception:
        live = None

    if live and live > 0:
        _CACHE["fx_source"] = SOURCE_FLUTTERWAVE
        _CACHE["usdt_ngn"] = live
        return live

    tether_ngn = (coingecko or {}).get("tether_ngn", 0.0)
    if tether_ngn > 0:
        _CACHE["fx_source"] = SOURCE_COINGECKO
        _CACHE["usdt_ngn"] = tether_ngn
        return tether_ngn

    static_rate = _static_usdt_ngn_rate()
    _CACHE["fx_source"] = SOURCE_STATIC
    _CACHE["usdt_ngn"] = static_rate
    return static_rate


def get_last_usdt_ngn_rate() -> float:
    """The USDT/NGN rate behind the most recent NGN price."""
    return _safe_float(_CACHE.get("usdt_ngn"), _static_usdt_ngn_rate())


async def _dedust_usd_rate() -> Optional[float]:
    """Live USD price of 1 IDIA from DeDust pools, or None if unpriced."""
    try:
        rate = await dedust.fetch_idia_usd_rate()
    except Exception:
        return None
    return rate if rate and rate > 0 else None


async def _coingecko_prices() -> dict[str, float]:
    """
    CoinGecko IDIA + tether prices. Empty dict when IDIA is not listed
    or IDIA_COINGECKO_ID is unset.
    """
    cg_id = os.getenv("IDIA_COINGECKO_ID", "")
    if not cg_id:
        return {}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": f"{cg_id},tether", "vs_currencies": "ngn,usd"},
            )
            r.raise_for_status()
            payload = r.json()
    except Exception:
        return {}

    out: dict[str, float] = {}
    idia_usd = _safe_float(payload.get(cg_id, {}).get("usd"), 0.0)
    idia_ngn = _safe_float(payload.get(cg_id, {}).get("ngn"), 0.0)
    tether_ngn = _safe_float(payload.get("tether", {}).get("ngn"), 0.0)
    if idia_usd > 0:
        out["idia_usd"] = idia_usd
    if idia_ngn > 0:
        out["idia_ngn"] = idia_ngn
    if tether_ngn > 0:
        out["tether_ngn"] = tether_ngn
    return out


async def fetch_idia_usdt_rate() -> float:
    """Return the current USD price of 1 IDIA coin (cached 2 min)."""
    now = int(time.time())
    if _CACHE.get("ts_usdt", 0) + _CACHE_TTL > now:
        cached = _CACHE.get("rate_usdt")
        if cached:
            return float(cached)

    rate = await _dedust_usd_rate()
    source = SOURCE_DEDUST

    if rate is None:
        prices = await _coingecko_prices()
        if "idia_usd" in prices:
            rate, source = prices["idia_usd"], SOURCE_COINGECKO

    if rate is None:
        rate, source = _DEFAULT_USD_PER_IDIA, SOURCE_FALLBACK

    _CACHE["rate_usdt"] = rate
    _CACHE["ts_usdt"] = now
    _CACHE["source"] = source
    return rate


async def fetch_idia_ngn_rate() -> float:
    """Return the current NGN price of 1 IDIA coin (cached 2 min).

    Pricing priority:
    1) DeDust live pool price (IDIA->TON->USD) x USDT->NGN
    2) CoinGecko IDIA->NGN, else (IDIA->USD) x (USDT->NGN)
    3) Environment fallback IDIA_NGN_RATE

    The USDT->NGN leg comes from Flutterwave when configured.
    """
    now = int(time.time())
    if _CACHE.get("ts", 0) + _CACHE_TTL > now:
        cached = _CACHE.get("rate")
        if cached:
            return float(cached)

    rate: Optional[float] = None
    source = SOURCE_FALLBACK

    prices = await _coingecko_prices()
    usdt_ngn = await resolve_usdt_ngn_rate(prices)

    # 1) DeDust — the live market, when a TON/IDIA pool exists.
    dedust_usd = await _dedust_usd_rate()
    if dedust_usd:
        rate = dedust_usd * usdt_ngn
        source = SOURCE_DEDUST

    # 2) CoinGecko — direct NGN quote, else derived through USD.
    if rate is None or rate <= 0:
        if "idia_ngn" in prices:
            rate, source = prices["idia_ngn"], SOURCE_COINGECKO
        elif "idia_usd" in prices:
            rate = prices["idia_usd"] * usdt_ngn
            source = SOURCE_COINGECKO

    # 3) Configured fallback. Unless IDIA_NGN_RATE is pinned, convert the USD
    #    placeholder with the live FX rate so the naira leg still tracks the
    #    market even while IDIA itself has no traded price.
    if rate is None or rate <= 0:
        source = SOURCE_FALLBACK
        if _NGN_RATE_PINNED:
            rate = _DEFAULT_NGN_PER_IDIA
        else:
            rate = _DEFAULT_USD_PER_IDIA * usdt_ngn
        if rate <= 0:
            rate = _DEFAULT_NGN_PER_IDIA

    _CACHE["rate"] = rate
    _CACHE["ts"] = now
    _CACHE["source"] = source
    return rate


async def ngn_to_idia(ngn_amount: float) -> float:
    """Convert a NGN amount to idia coin units (6 decimal places)."""
    rate = await fetch_idia_ngn_rate()
    if rate <= 0:
        rate = _DEFAULT_NGN_PER_IDIA
    return round(ngn_amount / rate, 6)


def idia_to_ton_amount(idia: float) -> int:
    """Convert an idia coin float to the Jetton's smallest unit for transfer."""
    return int(round(idia * (10 ** IDIA_TON_DECIMALS)))
