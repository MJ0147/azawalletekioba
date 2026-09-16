"""
Proof that a visitor controls a TON wallet, from TON Connect's ton_proof sign-in.

The site hands the wallet a one-time payload. The wallet signs a message containing its address, the
site's domain, the time and that payload. The signature is checked against the wallet's public key,
read from the wallet state (walletStateInit) the wallet sends, after confirming that the state really
is this wallet's: a TON address is the hash of its state. Message format:
https://docs.ton.org/develop/dapps/ton-connect/sign
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
import struct
import time
from typing import Any, Iterator, Optional

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey
from tonsdk.boc import Cell
from tonsdk.utils import Address

PAYLOAD_TTL_SECONDS = 15 * 60
MAX_CLOCK_SKEW_SECONDS = 15 * 60
_PAYLOAD_BODY_CHARS = 32
_PAYLOAD_MAC_CHARS = 32
# Where standard wallet contracts keep their 256-bit public key in their data cell: v3 and v4 after
# the seqno and wallet id, v5 after one more flag bit, v2 right after the seqno.
_PUBLIC_KEY_BIT_OFFSETS = (64, 65, 32)


class TonProofError(ValueError):
    """The sign-in proof is missing, expired, for another site or wallet, or not validly signed."""


def _payload_mac(secret: str, body: str) -> str:
    return hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()[:_PAYLOAD_MAC_CHARS]


def new_payload(secret: str, now: Optional[float] = None) -> str:
    """A one-time sign-in challenge: an expiry and a random nonce, signed so nothing needs storing."""
    expires = int(now if now is not None else time.time()) + PAYLOAD_TTL_SECONDS
    body = f"{expires:08x}{secrets.token_hex(12)}"
    return body + _payload_mac(secret, body)


def check_payload(payload: Any, secret: str, now: Optional[float] = None) -> None:
    """Raise TonProofError unless `payload` is an unexpired challenge this site issued."""
    if not isinstance(payload, str) or len(payload) != _PAYLOAD_BODY_CHARS + _PAYLOAD_MAC_CHARS:
        raise TonProofError("the sign-in challenge is missing")
    body, mac = payload[:_PAYLOAD_BODY_CHARS], payload[_PAYLOAD_BODY_CHARS:]
    if not hmac.compare_digest(mac, _payload_mac(secret, body)):
        raise TonProofError("the sign-in challenge wasn't issued by this site")
    try:
        expires = int(body[:8], 16)
    except ValueError as exc:
        raise TonProofError("the sign-in challenge is malformed") from exc
    if expires < int(now if now is not None else time.time()):
        raise TonProofError("the sign-in challenge expired; try again")


def _state_init_data(state_init: Cell) -> Cell:
    """The data cell of a StateInit:
    split_depth:(Maybe ## 5) special:(Maybe TickTock) code:(Maybe ^Cell) data:(Maybe ^Cell) library:(Maybe ^Cell)
    """
    bits, refs = state_init.bits, state_init.refs
    position = 0
    if bits.get(position):  # split_depth
        position += 5
    position += 1
    if bits.get(position):  # special (tick, tock)
        position += 2
    position += 1
    ref_index = 0
    if bits.get(position):  # code
        ref_index += 1
    position += 1
    if not bits.get(position) or len(refs) <= ref_index:
        raise TonProofError("the wallet state has no data")
    return refs[ref_index]


def _candidate_public_keys(data: Cell) -> Iterator[bytes]:
    used = data.bits.cursor
    for offset in _PUBLIC_KEY_BIT_OFFSETS:
        if offset + 256 > used:
            continue
        value = 0
        for index in range(offset, offset + 256):
            value = (value << 1) | int(bool(data.bits.get(index)))
        yield value.to_bytes(32, "big")


def verify_proof(
    *,
    address: str,
    proof: dict[str, Any],
    state_init: str,
    allowed_domains: set[str],
    secret: str,
    now: Optional[float] = None,
) -> str:
    """Check a ton_proof sign-in. Returns the wallet's raw address ("0:<hex>"); raises TonProofError."""
    current = int(now if now is not None else time.time())
    try:
        timestamp = int(proof["timestamp"])
        domain = str(proof["domain"]["value"])
        domain_length = int(proof["domain"]["lengthBytes"])
        payload = proof["payload"]
        signature = base64.b64decode(str(proof["signature"]), validate=True)
        state_bytes = base64.b64decode(state_init, validate=True)
    except (KeyError, TypeError, ValueError, binascii.Error) as exc:
        raise TonProofError("the sign-in proof is incomplete") from exc
    # Addresses and wallet state come straight from the browser; tonsdk raises assorted errors on bad input.
    try:
        wallet = Address(address)
        state = Cell.one_from_boc(state_bytes)
    except Exception as exc:
        raise TonProofError("the wallet address or state is unreadable") from exc

    domain_bytes = domain.encode("utf-8")
    if domain.lower() not in allowed_domains or domain_length != len(domain_bytes):
        raise TonProofError("the proof was made for a different site")
    if abs(current - timestamp) > MAX_CLOCK_SKEW_SECONDS:
        raise TonProofError("the proof is too old; try again")
    check_payload(payload, secret, current)
    if bytes(state.bytes_hash()) != bytes(wallet.hash_part):
        raise TonProofError("the wallet state doesn't belong to this address")

    message = (
        b"ton-proof-item-v2/"
        + struct.pack(">i", wallet.wc)
        + bytes(wallet.hash_part)
        + struct.pack("<I", domain_length)
        + domain_bytes
        + struct.pack("<Q", timestamp)
        + payload.encode("utf-8")
    )
    digest = hashlib.sha256(b"\xff\xff" + b"ton-connect" + hashlib.sha256(message).digest()).digest()
    for public_key in _candidate_public_keys(_state_init_data(state)):
        try:
            VerifyKey(public_key).verify(digest, signature)
        except (BadSignatureError, ValueError):
            continue
        return f"{wallet.wc}:{bytes(wallet.hash_part).hex()}"
    raise TonProofError("the wallet's signature doesn't match")
