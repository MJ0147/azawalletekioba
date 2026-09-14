import json
import os
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


TON_API_BASE = os.getenv("TON_API_BASE", "https://toncenter.com/api/v2")
TON_API_KEY = os.getenv("TON_API_KEY", "")


def _http_json(url: str, payload: dict[str, Any]
               | None = None) -> dict[str, Any]:
    body = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    request = Request(url=url, data=body, headers=headers,
                      method="POST" if payload is not None else "GET")
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Network error while calling payment provider: {exc}") from exc


def process_ton_payment(wallet: str, amount: float,
                        tx_hash: str) -> dict[str, Any]:
    if not tx_hash:
        raise RuntimeError("Missing TON transaction hash.")

    try:
        expected_nanotons = int(Decimal(str(amount)) * Decimal("1000000000"))
    except (InvalidOperation, ValueError) as exc:
        raise RuntimeError("Invalid TON amount.") from exc

    query = {"address": wallet, "limit": 30}
    if TON_API_KEY:
        query["api_key"] = TON_API_KEY
    endpoint = f"{TON_API_BASE}/getTransactions?{urlencode(query)}"
    response = _http_json(endpoint)

    if not response.get("ok", False):
        raise RuntimeError("TON API returned an unsuccessful response.")

    transactions = response.get("result", [])
    matched_tx = None
    for tx in transactions:
        tx_id = tx.get("transaction_id", {})
        if tx.get("hash") == tx_hash or tx_id.get("hash") == tx_hash:
            matched_tx = tx
            break

    if matched_tx is None:
        raise RuntimeError("TON transaction hash not found for this wallet.")

    in_msg = matched_tx.get("in_msg", {})
    observed_nanotons = int(in_msg.get("value", 0))
    if observed_nanotons < expected_nanotons:
        raise RuntimeError("TON payment amount is lower than expected.")

    return {
        "verified": True,
        "network": "ton-mainnet",
        "tx_hash": tx_hash,
        "wallet": wallet,
        "required_nanotons": expected_nanotons,
        "observed_nanotons": observed_nanotons,
    }


def verify_ton_transaction(wallet_address: str, tx_hash: str) -> bool:
    if not tx_hash or not wallet_address:
        return False

    query = {"address": wallet_address, "hash": tx_hash, "limit": 1}
    if TON_API_KEY:
        query["api_key"] = TON_API_KEY
    endpoint = f"{TON_API_BASE}/getTransactions?{urlencode(query)}"

    try:
        response = _http_json(endpoint)
    except RuntimeError:
        return False

    if not response.get("ok", False):
        return False

    result = response.get("result")
    return bool(result)
