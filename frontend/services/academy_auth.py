"""
Sign-in sessions and admin access for the Edo Language Academy.

After a TON wallet proves ownership (services/ton_proof.py), the learner gets a signed cookie naming
that wallet. It's signed with ACADEMY_SESSION_SECRET, or SECRET_KEY when that isn't set; without
either, sign-in stays off. Reviewing IDIA conversions needs `Authorization: Bearer <ACADEMY_ADMIN_TOKEN>`.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
import time
from typing import Optional
from urllib.parse import urlsplit

SESSION_COOKIE = "academy_session"
SESSION_SECONDS = 30 * 24 * 60 * 60


def session_secret() -> str:
    return (os.getenv("ACADEMY_SESSION_SECRET") or os.getenv("SECRET_KEY") or "").strip()


def _mac(secret: str, body: str) -> str:
    return hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()


def make_session(address: str, secret: str, now: Optional[float] = None) -> str:
    expires = int(now if now is not None else time.time()) + SESSION_SECONDS
    body = f"{address}|{expires}"
    token = f"{body}|{_mac(secret, body)}"
    return base64.urlsafe_b64encode(token.encode("utf-8")).decode("ascii").rstrip("=")


def read_session(token: Optional[str], secret: str, now: Optional[float] = None) -> Optional[str]:
    """The wallet a session cookie names, or None if it's missing, forged or expired."""
    if not token or not secret:
        return None
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode("utf-8")
        address, expires, mac = raw.rsplit("|", 2)
        expires_at = int(expires)
    except (ValueError, binascii.Error, UnicodeDecodeError):
        return None
    if not hmac.compare_digest(mac, _mac(secret, f"{address}|{expires}")):
        return None
    if expires_at < int(now if now is not None else time.time()):
        return None
    return address


def proof_domains(request_host: str) -> set[str]:
    """Domains a wallet sign-in may name: the host serving this request, PUBLIC_BASE_URL's host, and any
    extra ACADEMY_PROOF_DOMAINS."""
    candidates = [
        request_host or "",
        urlsplit(os.getenv("PUBLIC_BASE_URL", "")).netloc,
        *os.getenv("ACADEMY_PROOF_DOMAINS", "").split(","),
    ]
    domains: set[str] = set()
    for candidate in candidates:
        host = candidate.split(",")[0].strip().lower()
        if host:
            domains.add(host)
            domains.add(host.split(":")[0])
    return domains


def is_admin(authorization: Optional[str]) -> bool:
    """True for `Bearer <ACADEMY_ADMIN_TOKEN>`. Always False while no token is configured."""
    token = os.getenv("ACADEMY_ADMIN_TOKEN", "").strip()
    if not token or not authorization:
        return False
    scheme, _, supplied = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return False
    return hmac.compare_digest(supplied.strip().encode("utf-8"), token.encode("utf-8"))
