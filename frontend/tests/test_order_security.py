"""
Order integrity: admin-only order reads, insert-only recording, and payment
verification bound to the merchant's Jetton wallet, the order comment and the
order amount.
"""
from __future__ import annotations

import asyncio
import base64
import sys
from pathlib import Path

import pytest

FRONTEND_DIR = Path(__file__).resolve().parent.parent
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from services import orders  # noqa: E402

# ── admin guard ──────────────────────────────────────────────────────────


def test_is_admin_closed_when_no_token_configured(monkeypatch) -> None:
    monkeypatch.setattr(orders, "ORDERS_ADMIN_TOKEN", "")
    assert not orders.is_admin("Bearer anything")
    assert not orders.is_admin("Bearer ")


def test_is_admin_requires_exact_bearer_token(monkeypatch) -> None:
    monkeypatch.setattr(orders, "ORDERS_ADMIN_TOKEN", "s3cret")
    assert orders.is_admin("Bearer s3cret")
    assert orders.is_admin("bearer s3cret")
    assert not orders.is_admin(None)
    assert not orders.is_admin("s3cret")
    assert not orders.is_admin("Basic s3cret")
    assert not orders.is_admin("Bearer wrong")
    assert not orders.is_admin("Bearer sécret")


# ── recording never overwrites ───────────────────────────────────────────


class _FakeQuery:
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    def insert(self, row):
        self._calls.append("insert")
        return self

    def upsert(self, row, **kwargs):
        self._calls.append("upsert")
        return self

    async def execute(self):
        return None


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def table(self, name):
        return _FakeQuery(self.calls)


def test_record_inserts_and_never_upserts(monkeypatch) -> None:
    client = _FakeClient()

    async def fake_get_client(service: bool = False):
        return client

    monkeypatch.setattr(orders, "is_enabled", lambda: True)
    monkeypatch.setattr(orders.supabase_client, "get_client", fake_get_client)

    stored = asyncio.run(
        orders.record({"order_id": "ABC", "product": "x", "amount_ngn": 1, "amount_idia": 1})
    )
    assert stored is True
    assert client.calls == ["insert"]


# ── on-chain verification ────────────────────────────────────────────────

tonsdk = pytest.importorskip("tonsdk")

from tonsdk.boc import begin_cell  # noqa: E402
from tonsdk.utils import Address  # noqa: E402

from services import ton  # noqa: E402


def _addr(byte: str) -> str:
    return Address("0:" + byte * 32).to_string(
        is_user_friendly=True, is_url_safe=True, is_bounceable=True
    )


MERCHANT = _addr("11")
MERCHANT_JETTON_WALLET = _addr("22")
SHOPPER = _addr("33")
ATTACKER_JETTON_WALLET = _addr("44")

HASH_A = base64.b64encode(b"\x01" * 32).decode()
HASH_B = base64.b64encode(b"\x02" * 32).decode()


def _notification(units: int, comment: str, sender: str = SHOPPER) -> str:
    forward = begin_cell().store_uint(0, 32).store_string(comment).end_cell()
    body = (
        begin_cell()
        .store_uint(ton.TRANSFER_NOTIFICATION_OP, 32)
        .store_uint(7, 64)
        .store_coins(units)
        .store_address(Address(sender))
        .store_bit(1)
        .store_ref(forward)
        .end_cell()
    )
    return base64.b64encode(body.to_boc(False)).decode()


def _tx(tx_hash: str, source: str, body: str) -> dict:
    return {
        "transaction_id": {"hash": tx_hash},
        "in_msg": {"source": source, "msg_data": {"@type": "msg.dataRaw", "body": body}},
    }


def _verify(monkeypatch, transactions, comment="EKIOBA-ORDER1", amount=10.0, tx_hash=None):
    async def fake_jetton_wallet(merchant: str) -> str:
        return MERCHANT_JETTON_WALLET

    async def fake_get_transactions(address: str):
        assert address == MERCHANT
        return transactions

    monkeypatch.setattr(ton, "_merchant_jetton_wallet", fake_jetton_wallet)
    monkeypatch.setattr(ton, "_get_transactions", fake_get_transactions)
    return asyncio.run(ton.verify_jetton_payment(MERCHANT, comment, amount, tx_hash))


def test_parse_transfer_notification_roundtrip() -> None:
    note = ton.parse_transfer_notification(_notification(12345, "EKIOBA-ORDER1"))
    assert note == {"amount": 12345, "sender": SHOPPER, "comment": "EKIOBA-ORDER1"}


def test_parse_rejects_other_messages() -> None:
    other = begin_cell().store_uint(ton.JETTON_TRANSFER_OP, 32).end_cell()
    assert ton.parse_transfer_notification(base64.b64encode(other.to_boc(False)).decode()) is None
    assert ton.parse_transfer_notification("not-a-boc") is None


def test_verify_confirms_matching_payment(monkeypatch) -> None:
    units = ton.to_jetton_units(10.0)
    result = _verify(
        monkeypatch, [_tx(HASH_A, MERCHANT_JETTON_WALLET, _notification(units, "EKIOBA-ORDER1"))]
    )
    assert result["verified"] is True
    assert result["tx_hash"] == HASH_A


def test_verify_rejects_payment_for_another_order(monkeypatch) -> None:
    units = ton.to_jetton_units(10.0)
    result = _verify(
        monkeypatch, [_tx(HASH_A, MERCHANT_JETTON_WALLET, _notification(units, "EKIOBA-OTHER"))]
    )
    assert result["verified"] is False
    assert result["status"] == "not-found"


def test_verify_rejects_forged_jetton(monkeypatch) -> None:
    units = ton.to_jetton_units(10.0)
    result = _verify(
        monkeypatch, [_tx(HASH_A, ATTACKER_JETTON_WALLET, _notification(units, "EKIOBA-ORDER1"))]
    )
    assert result["verified"] is False


def test_verify_rejects_underpayment(monkeypatch) -> None:
    units = ton.to_jetton_units(10.0) - 1
    result = _verify(
        monkeypatch, [_tx(HASH_A, MERCHANT_JETTON_WALLET, _notification(units, "EKIOBA-ORDER1"))]
    )
    assert result["verified"] is False
    assert result["status"] == "underpaid"


def test_verify_honours_requested_tx_hash(monkeypatch) -> None:
    units = ton.to_jetton_units(10.0)
    txs = [_tx(HASH_A, MERCHANT_JETTON_WALLET, _notification(units, "EKIOBA-ORDER1"))]

    assert _verify(monkeypatch, txs, tx_hash=HASH_B)["verified"] is False
    assert _verify(monkeypatch, txs, tx_hash=(b"\x01" * 32).hex())["verified"] is True
    assert _verify(monkeypatch, txs, tx_hash="garbage")["status"] == "invalid-tx-hash"
