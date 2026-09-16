"""
Log in to the website with Telegram, using the Telegram Login Widget for the site's bot (@IdiacoinBot).

Telegram signs the login data with a key derived from the bot token; the website checks that
signature, then keeps a signed session cookie naming the Telegram account. Accounts listed in
TELEGRAM_ADMIN_IDS or TELEGRAM_ADMIN_USERNAMES get the site's admin rights: reviewing IDIA
conversions, orders and Iyobo's knowledge queue. Numeric ids are safer than usernames, which can
change hands.

Signature check: https://core.telegram.org/widgets/login-legacy
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Mapping, Optional
from urllib.parse import parse_qsl

from fastapi import Request

from services.academy_auth import make_session, read_session, session_secret

SESSION_COOKIE = "ekioba_telegram"
MAX_LOGIN_AGE_SECONDS = 24 * 60 * 60
# Mini App data is made fresh each time the app opens, so it does not need the widget's long
# window, and a shorter one limits how long captured initData could be replayed.
MAX_MINI_APP_AGE_SECONDS = 60 * 60
# Telegram signs Mini App data with a key derived from this constant, not with the bot token
# directly as the login widget does.
MINI_APP_SECRET_SALT = b"WebAppData"
# hash carries the HMAC itself; signature is the separate Ed25519 field for third parties.
MINI_APP_UNSIGNED_FIELDS = ("hash", "signature")
# The fields Telegram signs. Anything else on the callback URL (such as our own `next`) isn't signed.
TELEGRAM_FIELDS = ("id", "first_name", "last_name", "username", "photo_url", "auth_date")
DEFAULT_BOT_USERNAME = "IdiacoinBot"
DEFAULT_ADMIN_USERNAMES = "Azavault,Ramseyaimua"
# The same two admins by numeric id: @Azavault and @Ramseyaimua. A Telegram id is permanent, while a
# username can be released and taken by someone else, so these are the safer half of the check.
DEFAULT_ADMIN_IDS = "8894431525,7152238199"


class TelegramLoginError(ValueError):
    """The login data is missing, expired or not signed by Telegram for this bot."""


@dataclass(frozen=True)
class TelegramUser:
    id: int
    username: str = ""


def bot_token() -> str:
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


def bot_username() -> str:
    return os.getenv("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@") or DEFAULT_BOT_USERNAME


def is_configured() -> bool:
    return bool(bot_token() and session_secret())


def verify_login(fields: Mapping[str, Any], token: str, now: Optional[float] = None) -> TelegramUser:
    """Check the data Telegram sent after login. Raises TelegramLoginError unless it's genuine and fresh."""
    if not token:
        raise TelegramLoginError("Telegram login isn't set up on this site yet")
    received = {key: str(fields[key]) for key in TELEGRAM_FIELDS if key in fields and fields[key] is not None}
    supplied = str(fields.get("hash") or "").strip().lower()
    data_check_string = "\n".join(f"{key}={received[key]}" for key in sorted(received))
    secret_key = hashlib.sha256(token.encode("utf-8")).digest()
    expected = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not supplied or not hmac.compare_digest(expected, supplied):
        raise TelegramLoginError("this login didn't come from Telegram")
    try:
        user_id = int(received["id"])
        auth_date = int(received["auth_date"])
    except (KeyError, ValueError) as exc:
        raise TelegramLoginError("the Telegram login is incomplete") from exc
    if int(now if now is not None else time.time()) - auth_date > MAX_LOGIN_AGE_SECONDS:
        raise TelegramLoginError("this Telegram login has expired; log in again")
    return TelegramUser(id=user_id, username=received.get("username", ""))


def verify_mini_app(init_data: str, token: str, now: Optional[float] = None) -> TelegramUser:
    """Check the initData Telegram gives a Mini App. Raises TelegramLoginError unless it is genuine.

    Telegram signs this differently from the login widget: the key is an HMAC of the bot token
    under the constant "WebAppData", rather than a plain SHA-256 of the token.
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not token:
        raise TelegramLoginError("Telegram login isn't set up on this site yet")
    if not init_data:
        raise TelegramLoginError("Telegram sent no sign-in data")

    # initData is a query string, so "+" decodes to a space and a literal "+" arrives as %2B.
    received: dict[str, str] = dict(parse_qsl(init_data, keep_blank_values=True))

    supplied = str(received.get("hash") or "").strip().lower()
    signed = {k: v for k, v in received.items() if k not in MINI_APP_UNSIGNED_FIELDS}
    data_check_string = "\n".join(f"{key}={signed[key]}" for key in sorted(signed))
    secret_key = hmac.new(MINI_APP_SECRET_SALT, token.encode("utf-8"), hashlib.sha256).digest()
    expected = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not supplied or not hmac.compare_digest(expected, supplied):
        raise TelegramLoginError("this sign-in didn't come from Telegram")

    try:
        auth_date = int(received["auth_date"])
        person = json.loads(received["user"])
        user_id = int(person["id"])
    except (KeyError, ValueError, TypeError) as exc:
        raise TelegramLoginError("the Telegram sign-in is incomplete") from exc
    if int(now if now is not None else time.time()) - auth_date > MAX_MINI_APP_AGE_SECONDS:
        raise TelegramLoginError("this Telegram sign-in has expired; reopen the app")
    return TelegramUser(id=user_id, username=str(person.get("username") or ""))


def session_for(user: TelegramUser, secret: str) -> str:
    return make_session(f"{user.id}:{user.username}", secret)


def current_user(request: Request) -> Optional[TelegramUser]:
    subject = read_session(request.cookies.get(SESSION_COOKIE), session_secret())
    if not subject:
        return None
    user_id, _, username = subject.partition(":")
    try:
        return TelegramUser(id=int(user_id), username=username)
    except ValueError:
        return None


def _names(variable: str, default: str = "") -> set[str]:
    return {name for name in (part.strip().lstrip("@").lower() for part in os.getenv(variable, default).split(",")) if name}


def is_admin(user: Optional[TelegramUser]) -> bool:
    """Admins are checked on every request, so removing someone from the settings takes effect at once."""
    if user is None:
        return False
    if str(user.id) in _names("TELEGRAM_ADMIN_IDS", DEFAULT_ADMIN_IDS):
        return True
    return bool(user.username) and user.username.lower() in _names("TELEGRAM_ADMIN_USERNAMES", DEFAULT_ADMIN_USERNAMES)


def request_is_admin(request: Request) -> bool:
    return is_admin(current_user(request))
