"""
TON blockchain service — Idia Jetton transfers over TON Connect.

Responsibilities:
  * resolve the *sender's* Jetton wallet for the IDIA Jetton master
    (a Jetton transfer message must be addressed to the sender's own
    Jetton wallet contract, never to the merchant's main wallet);
  * build a TL-B encoded `transfer#0f8a7ea5` body and serialise it to a
    base64 BOC that TON Connect can hand to the wallet;
  * normalise the raw (`0:<hex>`) addresses TON Connect returns into the
    user-friendly form the rest of the app and the TON APIs expect.
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Any, Optional

import httpx

logger = logging.getLogger("ekioba.ton")

try:  # tonsdk is required for on-chain payload construction
    from tonsdk.boc import Cell, begin_cell
    from tonsdk.utils import Address

    TON_SDK_AVAILABLE = True
except Exception:  # pragma: no cover - exercised only on broken installs
    Cell = None  # type: ignore[assignment]
    begin_cell = None  # type: ignore[assignment]
    Address = None  # type: ignore[assignment]

    TON_SDK_AVAILABLE = False


class TonServiceError(RuntimeError):
    """Raised when a TON payment request cannot be built."""


# IDIA Jetton master on TON mainnet (symbol "Idia", 9 decimals).
IDIA_TON_JETTON_ADDRESS = os.getenv(
    "IDIA_TON_JETTON_ADDRESS",
    os.getenv("TON_CONTRACT_ADDRESS", "EQC8QIjU-uXwrlj9B9Zc0ZBIaTS5TLzFb6djJIRwyLa6Enqs"),
)
IDIA_TON_DECIMALS = int(os.getenv("IDIA_TON_DECIMALS", "9"))

TON_API_BASE = os.getenv("TON_API_BASE", "https://toncenter.com/api/v2").rstrip("/")
TON_API_KEY = os.getenv("TON_API_KEY", "")

# TON attached to the transfer message to pay for gas, and the slice of it
# forwarded to the recipient so the transfer notification (carrying our order
# comment) is actually delivered. Both in nanotons.
TON_TRANSFER_GAS_NANOTON = int(os.getenv("TON_TRANSFER_GAS_NANOTON", "50000000"))  # 0.05 TON
TON_FORWARD_NANOTON = int(os.getenv("TON_FORWARD_NANOTON", "1"))  # 1 nanoton

JETTON_TRANSFER_OP = 0x0F8A7EA5
TEXT_COMMENT_OP = 0x00000000


def _require_sdk() -> None:
    if not TON_SDK_AVAILABLE:
        raise TonServiceError(
            "tonsdk is not installed; TON payments are unavailable. "
            "Install it with 'pip install tonsdk'."
        )


def is_valid_address(value: str) -> bool:
    """True when `value` parses as a TON address (raw or user-friendly)."""
    if not value or not TON_SDK_AVAILABLE:
        return False
    try:
        Address(value)
    except Exception:
        return False
    return True


def normalize_address(value: str, bounceable: bool = True) -> str:
    """
    Return the user-friendly form of a TON address.

    TON Connect reports accounts in raw `0:<hex>` form; TON APIs and humans
    both want the base64url form, so convert once at the boundary.
    """
    _require_sdk()
    try:
        return Address(value).to_string(
            is_user_friendly=True, is_url_safe=True, is_bounceable=bounceable
        )
    except Exception as exc:
        raise TonServiceError("Invalid TON address: " + repr(value)) from exc


def to_jetton_units(idia_amount: float) -> int:
    """Convert an IDIA float amount into the Jetton's smallest unit."""
    units = int(round(idia_amount * (10 ** IDIA_TON_DECIMALS)))
    if units <= 0:
        raise TonServiceError("IDIA amount is too small to transfer.")
    return units


def build_comment_cell(comment: str):
    """A standard TON text-comment cell (32 zero bits + UTF-8 text)."""
    _require_sdk()
    return begin_cell().store_uint(TEXT_COMMENT_OP, 32).store_string(comment).end_cell()


def build_jetton_transfer_payload(
    jetton_units: int,
    destination: str,
    response_destination: str,
    comment: str,
    forward_ton_amount: int = TON_FORWARD_NANOTON,
    query_id: int = 0,
) -> str:
    """
    Build the base64 BOC body for a Jetton `transfer` message.

    TL-B:
        transfer#0f8a7ea5 query_id:uint64 amount:(VarUInteger 16)
          destination:MsgAddress response_destination:MsgAddress
          custom_payload:(Maybe ^Cell) forward_ton_amount:(VarUInteger 16)
          forward_payload:(Either Cell ^Cell) = InternalMsgBody;
    """
    _require_sdk()
    body = (
        begin_cell()
        .store_uint(JETTON_TRANSFER_OP, 32)
        .store_uint(query_id, 64)
        .store_coins(jetton_units)
        .store_address(Address(destination))
        .store_address(Address(response_destination))
        .store_bit(0)  # custom_payload: nothing
        .store_coins(forward_ton_amount)
        .store_bit(1)  # forward_payload stored in a reference
        .store_ref(build_comment_cell(comment))
        .end_cell()
    )
    return base64.b64encode(body.to_boc(False)).decode()


# Set once the TON API rejects our key, so we stop sending it. An invalid key
# is worse than no key: toncenter answers anonymous requests (rate limited) but
# 401s an unrecognised one, which would fail every payment.
_api_key_rejected = False


def _toncenter_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if TON_API_KEY and not _api_key_rejected:
        headers["X-API-Key"] = TON_API_KEY
    return headers


def api_key_status() -> str:
    """'rejected', 'active' or 'absent' - surfaced by diagnostics."""
    if not TON_API_KEY:
        return "absent"
    return "rejected" if _api_key_rejected else "active"


async def run_get_method(
    address: str,
    method: str,
    stack: list[Any] | None = None,
) -> dict[str, Any]:
    """
    Call a get-method on a TON contract via the TON HTTP API.

    If the configured API key is rejected, fall back to an anonymous request
    once and stop sending the key. Anonymous access is rate limited but works;
    a bad key fails outright.
    """
    global _api_key_rejected

    payload = {"address": address, "method": method, "stack": stack or []}

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{TON_API_BASE}/runGetMethod", json=payload, headers=_toncenter_headers()
        )

        if response.status_code == 401 and TON_API_KEY and not _api_key_rejected:
            _api_key_rejected = True
            logger.warning(
                "TON_API_KEY was rejected by %s (401). Falling back to "
                "anonymous, rate-limited access. Check that the key is a "
                "toncenter key - keys for TonAPI or TON Access are not "
                "interchangeable.",
                TON_API_BASE,
            )
            response = await client.post(
                f"{TON_API_BASE}/runGetMethod",
                json=payload,
                headers=_toncenter_headers(),
            )

        response.raise_for_status()
        return response.json()


# Backwards-compatible private alias.
_run_get_method = run_get_method


async def get_jetton_wallet_address(
    owner_address: str,
    jetton_master: Optional[str] = None,
) -> str:
    """
    Resolve the Jetton wallet contract that holds `owner_address`'s IDIA.

    This is the address a TON Connect transfer message must target.
    """
    _require_sdk()
    master = jetton_master or IDIA_TON_JETTON_ADDRESS
    if not is_valid_address(master):
        raise TonServiceError(
            "IDIA Jetton master address is invalid: " + repr(master)
            + ". Set IDIA_TON_JETTON_ADDRESS to a valid TON address."
        )

    owner_cell = begin_cell().store_address(Address(owner_address)).end_cell()
    owner_slice = base64.b64encode(owner_cell.to_boc(False)).decode()

    try:
        payload = await _run_get_method(
            master, "get_wallet_address", [["tvm.Slice", owner_slice]]
        )
    except httpx.HTTPError as exc:
        raise TonServiceError(f"TON API unavailable: {exc}") from exc

    result = payload.get("result") or {}
    if result.get("exit_code") != 0:
        raise TonServiceError(
            "TON API could not resolve the sender's Jetton wallet "
            f"(exit_code={result.get('exit_code')})."
        )

    try:
        entry = result["stack"][0]
        wallet_boc = base64.b64decode(entry[1]["bytes"])
        wallet_address = Cell.one_from_boc(wallet_boc).begin_parse().read_msg_addr()
    except Exception as exc:
        raise TonServiceError("Malformed response from the TON API.") from exc

    return wallet_address.to_string(
        is_user_friendly=True, is_url_safe=True, is_bounceable=True
    )


# A Jetton wallet sends this to its *owner* when tokens arrive:
#   transfer_notification#7362d09c query_id:uint64 amount:(VarUInteger 16)
#     sender:MsgAddress forward_payload:(Either Cell ^Cell)
TRANSFER_NOTIFICATION_OP = 0x7362D09C
TON_VERIFY_TX_LIMIT = int(os.getenv("TON_VERIFY_TX_LIMIT", "50"))

_merchant_jetton_wallets: dict[str, str] = {}


def parse_transfer_notification(body_boc_b64: str) -> Optional[dict[str, Any]]:
    """
    Decode a Jetton `transfer_notification` message body.

    Returns {"amount": int, "sender": str | None, "comment": str | None}, or
    None when the body is not a transfer notification.
    """
    _require_sdk()
    try:
        body = Cell.one_from_boc(base64.b64decode(body_boc_b64)).begin_parse()
        if len(body) < 32 or body.read_uint(32) != TRANSFER_NOTIFICATION_OP:
            return None
        body.read_uint(64)  # query_id
        amount = body.read_coins()
        sender = body.read_msg_addr()

        forward = body
        if len(body) and body.read_bit():
            forward = body.read_ref().begin_parse()

        comment = None
        if len(forward) >= 32 and forward.read_uint(32) == TEXT_COMMENT_OP:
            comment = forward.read_string()
    except Exception:
        return None

    return {
        "amount": amount,
        "sender": sender.to_string(
            is_user_friendly=True, is_url_safe=True, is_bounceable=True
        ) if sender else None,
        "comment": comment,
    }


def _hash_bytes(value: Optional[str]) -> Optional[bytes]:
    """A 32-byte transaction hash from its hex or base64 spelling."""
    value = (value or "").strip()
    if len(value) == 64:
        try:
            return bytes.fromhex(value)
        except ValueError:
            pass
    unpadded = value.rstrip("=").replace("+", "-").replace("/", "_")
    try:
        raw = base64.urlsafe_b64decode(unpadded + "=" * (-len(unpadded) % 4))
    except Exception:
        return None
    return raw if len(raw) == 32 else None


async def _merchant_jetton_wallet(merchant_wallet: str) -> str:
    """The merchant's IDIA Jetton wallet; it never changes, so cache it."""
    if merchant_wallet not in _merchant_jetton_wallets:
        _merchant_jetton_wallets[merchant_wallet] = normalize_address(
            await get_jetton_wallet_address(merchant_wallet)
        )
    return _merchant_jetton_wallets[merchant_wallet]


async def _get_transactions(address: str) -> Optional[list[dict[str, Any]]]:
    """Recent transactions on `address`, or None when the TON API is unusable."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{TON_API_BASE}/getTransactions",
                params={"address": address, "limit": TON_VERIFY_TX_LIMIT},
                headers=_toncenter_headers(),
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    if not payload.get("ok", False):
        return None
    return payload.get("result") or []


async def verify_jetton_payment(
    merchant_wallet: str,
    comment: str,
    amount_idia: float,
    tx_hash: Optional[str] = None,
) -> dict[str, Any]:
    """
    Find the IDIA transfer that pays one specific order.

    A match must be a `transfer_notification` delivered to the merchant wallet
    by the merchant's own IDIA Jetton wallet (so a look-alike Jetton cannot
    forge one), carry exactly `comment`, and move at least `amount_idia`.
    When `tx_hash` is given, only that transaction is considered.
    """
    _require_sdk()
    if not is_valid_address(merchant_wallet):
        raise TonServiceError("TON_MERCHANT_WALLET is not configured or invalid.")

    merchant = normalize_address(merchant_wallet)
    jetton_wallet = await _merchant_jetton_wallet(merchant)
    expected_units = to_jetton_units(amount_idia)

    wanted_hash = _hash_bytes(tx_hash) if tx_hash else None
    if tx_hash and wanted_hash is None:
        return {"verified": False, "tx_hash": tx_hash, "status": "invalid-tx-hash"}

    transactions = await _get_transactions(merchant)
    if transactions is None:
        return {"verified": False, "tx_hash": tx_hash, "status": "api-unavailable"}

    status = "not-found"
    for tx in transactions:
        found_hash = (tx.get("transaction_id") or {}).get("hash") or ""
        if wanted_hash is not None and _hash_bytes(found_hash) != wanted_hash:
            continue

        in_msg = tx.get("in_msg") or {}
        source = in_msg.get("source") or ""
        if not is_valid_address(source) or normalize_address(source) != jetton_wallet:
            continue

        body = (in_msg.get("msg_data") or {}).get("body")
        note = parse_transfer_notification(body) if body else None
        if not note or note["comment"] != comment:
            continue

        if note["amount"] < expected_units:
            status = "underpaid"
            continue

        return {
            "verified": True,
            "tx_hash": found_hash,
            "status": "confirmed",
            "sender": note["sender"],
        }

    return {"verified": False, "tx_hash": tx_hash, "status": status}
