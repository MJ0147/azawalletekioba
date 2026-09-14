"""
DeDust price service — live IDIA Coin pricing from DeDust liquidity pools.

Why this reads DeDust's contracts rather than its REST API: DeDust's public
HTTP API exposes the whole pool set at `GET /v2/pools` (~5 MB, ~60 s) and has
no single-pool endpoint, so it cannot serve a per-request price. The pools
themselves are on-chain, so we ask them directly through the TON API:

    1. DeDust's Factory derives a pool address deterministically from the
       asset pair via `get_pool_address`, so no pool lookup table is needed.
    2. The pool contract's `get_reserves` returns live reserves.
    3. For a constant-product ("volatile") pool, the spot price of asset1 in
       asset0 is simply reserve0 / reserve1, adjusted for decimals.

IDIA is priced through two DeDust pools — TON/IDIA for the IDIA→TON leg and
TON/USDT for the TON→USD leg.

When no TON/IDIA pool exists yet, `get_reserves` fails with exit code -13
(account not deployed) and every public function here returns None so the
caller can fall back. Once the pool is created, pricing starts working with
no code change.
"""
from __future__ import annotations

import base64
import os
import time
from typing import Any, Optional

from services.ton import (
    IDIA_TON_DECIMALS,
    IDIA_TON_JETTON_ADDRESS,
    TON_SDK_AVAILABLE,
    run_get_method,
)

if TON_SDK_AVAILABLE:  # pragma: no branch - mirrors services.ton
    from tonsdk.boc import Cell, begin_cell
    from tonsdk.utils import Address
else:  # pragma: no cover
    Cell = None  # type: ignore[assignment]
    begin_cell = None  # type: ignore[assignment]
    Address = None  # type: ignore[assignment]

# DeDust Factory on TON mainnet.
DEDUST_FACTORY_ADDRESS = os.getenv(
    "DEDUST_FACTORY_ADDRESS", "EQBfBWT7X2BHg9tXAxzhz2aKiNTU1tpt5NsiK0uSDW_YAJ67"
)

# Reference stablecoin pool used to convert the TON leg into USD.
USDT_JETTON_ADDRESS = os.getenv(
    "USDT_TON_JETTON_ADDRESS", "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"
)
USDT_DECIMALS = int(os.getenv("USDT_TON_DECIMALS", "6"))

TON_DECIMALS = 9

POOL_TYPE_VOLATILE = 0
POOL_TYPE_STABLE = 1

# Pool addresses are deterministic and permanent, so they are cached for the
# process lifetime. Reserves move with every swap, so they get a short TTL.
_RESERVES_TTL = int(os.getenv("DEDUST_CACHE_TTL", "60"))

_pool_address_cache: dict[tuple[str, int], Optional[str]] = {}
_reserves_cache: dict[str, tuple[float, Optional[tuple[int, int]]]] = {}


def _asset_native():
    """DeDust asset cell: `native$0000 = Asset;`"""
    return begin_cell().store_uint(0, 4).end_cell()


def _asset_jetton(address: str):
    """DeDust asset cell: `jetton$0001 workchain_id:int8 address:uint256 = Asset;`"""
    parsed = Address(address)
    return (
        begin_cell()
        .store_uint(1, 4)
        .store_int(parsed.wc, 8)
        .store_bytes(parsed.hash_part)
        .end_cell()
    )


def _to_slice_arg(cell) -> list[str]:
    return ["tvm.Slice", base64.b64encode(cell.to_boc(False)).decode()]


def _stack_int(entry: Any) -> int:
    """Read an integer from a TON API get-method stack entry."""
    value = entry[1]
    if isinstance(value, dict):
        value = value.get("number", {}).get("number", "0")
    return int(str(value), 0)


async def get_pool_address(
    jetton_address: str,
    pool_type: int = POOL_TYPE_VOLATILE,
) -> Optional[str]:
    """
    Derive the DeDust TON/<jetton> pool address from the Factory.

    Returns None if the SDK is missing or the Factory call fails. Note that a
    returned address is only *derived* — the pool may not be deployed.
    """
    if not TON_SDK_AVAILABLE:
        return None

    key = (jetton_address, pool_type)
    if key in _pool_address_cache:
        return _pool_address_cache[key]

    try:
        payload = await run_get_method(
            DEDUST_FACTORY_ADDRESS,
            "get_pool_address",
            [
                ["num", str(pool_type)],
                _to_slice_arg(_asset_native()),
                _to_slice_arg(_asset_jetton(jetton_address)),
            ],
        )
    except Exception:
        return None

    result = payload.get("result") or {}
    if result.get("exit_code") != 0:
        _pool_address_cache[key] = None
        return None

    try:
        pool_boc = base64.b64decode(result["stack"][0][1]["bytes"])
        address = (
            Cell.one_from_boc(pool_boc)
            .begin_parse()
            .read_msg_addr()
            .to_string(is_user_friendly=True, is_url_safe=True, is_bounceable=True)
        )
    except Exception:
        return None

    _pool_address_cache[key] = address
    return address


async def get_pool_reserves(pool_address: str) -> Optional[tuple[int, int]]:
    """
    Live (reserve0, reserve1) for a DeDust pool, in each asset's smallest unit.

    Returns None when the pool is not deployed (exit code -13) or the TON API
    is unreachable.
    """
    now = time.time()
    cached = _reserves_cache.get(pool_address)
    if cached and cached[0] + _RESERVES_TTL > now:
        return cached[1]

    reserves: Optional[tuple[int, int]] = None
    try:
        payload = await run_get_method(pool_address, "get_reserves", [])
        result = payload.get("result") or {}
        if result.get("exit_code") == 0:
            stack = result.get("stack") or []
            if len(stack) >= 2:
                reserve0 = _stack_int(stack[0])
                reserve1 = _stack_int(stack[1])
                if reserve0 > 0 and reserve1 > 0:
                    reserves = (reserve0, reserve1)
    except Exception:
        # Leave `reserves` as None; a transient failure must not be cached long.
        pass

    _reserves_cache[pool_address] = (now, reserves)
    return reserves


async def _ton_per_jetton(jetton_address: str, jetton_decimals: int) -> Optional[float]:
    """Spot price of one jetton denominated in TON, from its DeDust pool."""
    pool = await get_pool_address(jetton_address)
    if not pool:
        return None

    reserves = await get_pool_reserves(pool)
    if not reserves:
        return None

    # Asset order follows the Factory call: asset0 = native TON, asset1 = jetton.
    ton_reserve, jetton_reserve = reserves
    jetton_units = jetton_reserve / (10 ** jetton_decimals)
    if jetton_units <= 0:
        return None
    return (ton_reserve / (10 ** TON_DECIMALS)) / jetton_units


async def fetch_ton_usd_rate() -> Optional[float]:
    """USD price of 1 TON, via DeDust's TON/USDT pool."""
    ton_per_usdt = await _ton_per_jetton(USDT_JETTON_ADDRESS, USDT_DECIMALS)
    if not ton_per_usdt or ton_per_usdt <= 0:
        return None
    # ton_per_usdt is TON per 1 USDT; invert for USD per 1 TON.
    return 1.0 / ton_per_usdt


async def fetch_idia_ton_rate() -> Optional[float]:
    """TON price of 1 IDIA, via DeDust's TON/IDIA pool."""
    return await _ton_per_jetton(IDIA_TON_JETTON_ADDRESS, IDIA_TON_DECIMALS)


async def fetch_idia_usd_rate() -> Optional[float]:
    """
    USD price of 1 IDIA, derived entirely from DeDust pools:
    IDIA -> TON (TON/IDIA pool) -> USD (TON/USDT pool).
    """
    idia_ton = await fetch_idia_ton_rate()
    if not idia_ton or idia_ton <= 0:
        return None

    ton_usd = await fetch_ton_usd_rate()
    if not ton_usd or ton_usd <= 0:
        return None

    return idia_ton * ton_usd


async def get_market_snapshot() -> dict[str, Any]:
    """Diagnostic view of what DeDust currently reports for IDIA."""
    pool = await get_pool_address(IDIA_TON_JETTON_ADDRESS)
    reserves = await get_pool_reserves(pool) if pool else None
    idia_ton = await fetch_idia_ton_rate()
    ton_usd = await fetch_ton_usd_rate()

    return {
        "source": "dedust",
        "factory": DEDUST_FACTORY_ADDRESS,
        "idia_ton_pool": pool,
        "pool_deployed": reserves is not None,
        "reserves": (
            {"ton": reserves[0], "idia": reserves[1]} if reserves else None
        ),
        "ton_per_idia": idia_ton,
        "usd_per_ton": ton_usd,
        "usd_per_idia": (idia_ton * ton_usd) if (idia_ton and ton_usd) else None,
    }
