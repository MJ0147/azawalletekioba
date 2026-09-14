"""
Payment handler — orchestrates Idia Coin (IDIA) payments on TON.

TON is the only chain EKIOBA settles on. A payment request carries a
ready-to-sign TON Connect transaction: when the caller supplies the
connected wallet address we address a real Jetton transfer to that
wallet's Jetton contract; without it we can only return a deep link,
and the caller is told to reconnect and retry.
"""
from __future__ import annotations

import os
import sys
import time
import uuid
from typing import Any, Optional

# Allow importing from the services directory
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from services.idiaTokenService import ngn_to_idia
from services.ton import (
    IDIA_TON_JETTON_ADDRESS,
    TON_FORWARD_NANOTON,
    TON_TRANSFER_GAS_NANOTON,
    TonServiceError,
    build_jetton_transfer_payload,
    get_jetton_wallet_address,
    is_valid_address,
    normalize_address,
    to_jetton_units,
)

# How long the wallet has to sign the prepared transaction.
TON_TX_VALIDITY_SECONDS = int(os.getenv("TON_TX_VALIDITY_SECONDS", "600"))


def _merchant_wallet() -> str:
    wallet = os.getenv("TON_MERCHANT_WALLET", "").strip()
    if not wallet:
        raise ValueError("TON_MERCHANT_WALLET is not configured.")
    if not is_valid_address(wallet):
        raise ValueError("TON_MERCHANT_WALLET is not a valid TON address.")
    return normalize_address(wallet)


async def create_ton_payment_request(
    ngn_price: float,
    product_name: str,
    cart_items: Optional[list[dict[str, Any]]] = None,
    is_cart_checkout: bool = False,
    sender_address: Optional[str] = None,
) -> dict[str, Any]:
    """
    Create a TON Connect payment request for an IDIA Jetton transfer.

    Returns a payload the frontend hands straight to
    `tonConnectUI.sendTransaction(...)`.

    The order id is always minted here, never taken from the client: it keys
    the stored order and the on-chain comment, so a caller-chosen id could
    target someone else's order.
    """
    merchant_wallet = _merchant_wallet()

    idia_amount = await ngn_to_idia(ngn_price)
    oid = uuid.uuid4().hex[:16].upper()
    comment = f"EKIOBA-{oid}"

    result: dict[str, Any] = {
        "chain": "ton",
        "recipient": merchant_wallet,
        "jetton_address": IDIA_TON_JETTON_ADDRESS,
        "amount_idia": idia_amount,
        "amount_ngn": ngn_price,
        "order_id": oid,
        "comment": comment,
        "product": product_name,
        "is_cart_checkout": is_cart_checkout,
        "cart_items": cart_items or [],
        "cart_total_ngn": ngn_price if is_cart_checkout else 0,
        # Fallback for wallets opened outside TON Connect. It carries the gas
        # amount only — the Jetton itself moves via the TON Connect payload.
        "deeplink": (
            f"ton://transfer/{merchant_wallet}"
            f"?amount={TON_TRANSFER_GAS_NANOTON}&text={comment}"
        ),
    }

    if not sender_address:
        result["requires_sender"] = True
        result["message"] = (
            "Connect your TON wallet first so the IDIA transfer can be addressed "
            "to your Jetton wallet."
        )
        return result

    # A Jetton transfer is sent to the *sender's* Jetton wallet contract,
    # which then forwards the tokens on to the merchant.
    sender = normalize_address(sender_address)
    sender_jetton_wallet = await get_jetton_wallet_address(sender)

    payload = build_jetton_transfer_payload(
        jetton_units=to_jetton_units(idia_amount),
        destination=merchant_wallet,
        response_destination=sender,
        comment=comment,
        forward_ton_amount=TON_FORWARD_NANOTON,
        query_id=int(time.time()),
    )

    result["requires_sender"] = False
    result["sender"] = sender
    result["sender_jetton_wallet"] = sender_jetton_wallet
    result["ton_connect_tx"] = {
        "validUntil": int(time.time()) + TON_TX_VALIDITY_SECONDS,
        "from": sender,
        "messages": [
            {
                "address": sender_jetton_wallet,
                "amount": str(TON_TRANSFER_GAS_NANOTON),
                "payload": payload,
            }
        ],
    }
    return result


__all__ = ["create_ton_payment_request", "TonServiceError"]
