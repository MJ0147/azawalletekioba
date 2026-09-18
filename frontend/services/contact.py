"""The Contact Us form: check what a visitor wrote, then forward it to the EKIOBA inbox.

Delivery uses whichever provider is configured, in this order:

  * Resend (`RESEND_API_KEY`) — an HTTPS API. This is the one that works on Vercel, whose
    serverless runtime does not open outbound SMTP ports.
  * SMTP (`SMTP_HOST` with `SMTP_USERNAME` and `SMTP_PASSWORD`) — for the Docker and VM
    deployments. Gmail works here with an app password, not the account password.

With neither configured nothing can be sent, so `forward` raises ContactNotConfigured, the page
tells the visitor the address to write to directly, and the message is written to the log rather
than silently dropped.

The visitor's address goes in Reply-To, so answering the forwarded mail answers the visitor.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import smtplib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Optional

import httpx

logger = logging.getLogger("ekioba.contact")

# Where filled-in forms are sent. The deployment can point this somewhere else.
FORWARD_TO = os.getenv("CONTACT_FORWARD_TO", "adcredesolutions@gmail.com").strip()
RESEND_ENDPOINT = "https://api.resend.com/emails"
SEND_TIMEOUT = float(os.getenv("CONTACT_SEND_TIMEOUT", "15"))

MAX_NAME = 80
MAX_EMAIL = 254
MAX_SUBJECT = 120
MAX_MESSAGE = 4000
MIN_MESSAGE = 10
DEFAULT_SUBJECT = "Message from the EKIOBA website"

# One visitor, this many messages, within this many seconds.
RATE_LIMIT = int(os.getenv("CONTACT_RATE_LIMIT", "5"))
RATE_WINDOW = float(os.getenv("CONTACT_RATE_WINDOW", "600"))

# Deliberately permissive: an address either routes or it doesn't, and a strict pattern turns
# real addresses away. This only catches what is obviously not an address at all.
_EMAIL = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")
# A newline in a header field is how mail headers get forged; such a field is never legitimate.
_HEADER_BREAK = re.compile(r"[\r\n]")


class ContactError(Exception):
    """The message cannot be accepted or delivered. Its text is shown to the visitor."""


class ContactNotConfigured(ContactError):
    """No mail provider is set up, so nothing can be forwarded."""


@dataclass(frozen=True)
class ContactMessage:
    """One filled-in form, already checked."""

    name: str
    email: str
    subject: str
    message: str
    received_at: datetime

    def body(self) -> str:
        """The forwarded mail, as plain text."""
        when = self.received_at.strftime("%d %B %Y at %H:%M UTC")
        return (
            f"{self.message}\n\n"
            "—\n"
            f"From: {self.name} <{self.email}>\n"
            f"Sent: {when}\n"
            "Via: the Contact Us form on the EKIOBA website\n"
            f"Reply to this mail to answer {self.name} directly.\n"
        )

    def mail_subject(self) -> str:
        return f"[EKIOBA] {self.subject}"


def _one_line(value: object, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def validate(
    *,
    name: object,
    email: object,
    subject: object,
    message: object,
    honeypot: object = "",
) -> ContactMessage:
    """Check a submitted form. Raises ContactError with a sentence the visitor should read.

    `honeypot` is a field hidden from people by CSS; a browser leaves it empty and a form-filling
    bot does not.
    """
    if _one_line(honeypot, 100):
        raise ContactError("This message looks automated. If that's wrong, please email us directly.")

    clean_name = _one_line(name, MAX_NAME)
    if len(clean_name) < 2:
        raise ContactError("Please tell us your name.")

    clean_email = _one_line(email, MAX_EMAIL)
    if not _EMAIL.match(clean_email):
        raise ContactError("Please enter an email address we can reply to.")

    clean_subject = _one_line(subject, MAX_SUBJECT) or DEFAULT_SUBJECT

    # Only the body may contain line breaks; the rest become mail headers.
    if any(_HEADER_BREAK.search(field) for field in (clean_name, clean_email, clean_subject)):
        raise ContactError("Please remove the line breaks from your name, email and subject.")

    clean_message = str(message or "").strip()[:MAX_MESSAGE]
    if len(clean_message) < MIN_MESSAGE:
        raise ContactError(f"Please write a little more — at least {MIN_MESSAGE} characters.")

    return ContactMessage(
        name=clean_name,
        email=clean_email,
        subject=clean_subject,
        message=clean_message,
        received_at=datetime.now(timezone.utc),
    )


# Recent submissions per visitor. On serverless each instance keeps its own, so this thins out a
# naive flood rather than standing in for a real rate limiter.
_recent: dict[str, list[float]] = {}


def within_rate_limit(visitor: str) -> bool:
    """Whether this visitor may send another message now."""
    if not visitor or RATE_LIMIT <= 0:
        return True
    now = time.monotonic()
    times = [stamp for stamp in _recent.get(visitor, []) if now - stamp < RATE_WINDOW]
    if len(times) >= RATE_LIMIT:
        _recent[visitor] = times
        return False
    times.append(now)
    _recent[visitor] = times
    if len(_recent) > 2000:  # a long-lived process must not grow a dictionary forever
        for key in [k for k, stamps in _recent.items() if all(now - s >= RATE_WINDOW for s in stamps)]:
            _recent.pop(key, None)
    return True


def reset_rate_limit() -> None:
    """Forget every visitor's recent submissions. For tests."""
    _recent.clear()


# ── Delivery ────────────────────────────────────────────────────────────────


def _resend_key() -> str:
    return os.getenv("RESEND_API_KEY", "").strip()


def _smtp_settings() -> Optional[dict[str, object]]:
    host = os.getenv("SMTP_HOST", "").strip()
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    if not (host and username and password):
        return None
    port = int(os.getenv("SMTP_PORT", "465"))
    return {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        # Port 587 is the STARTTLS port; 465 is TLS from the first byte.
        "starttls": os.getenv("SMTP_STARTTLS", "").strip().lower() in {"1", "true", "yes", "on"} or port == 587,
    }


def sender_address() -> str:
    """Who the forwarded mail comes from."""
    configured = os.getenv("CONTACT_FROM", "").strip()
    if configured:
        return configured
    smtp = _smtp_settings()
    if smtp:
        # Mail servers reject a From that isn't the authenticated mailbox.
        return f"EKIOBA Contact Form <{smtp['username']}>"
    return "EKIOBA Contact Form <onboarding@resend.dev>"


def provider() -> str:
    """Which provider will be used: "resend", "smtp", or "" when none is configured."""
    if _resend_key():
        return "resend"
    return "smtp" if _smtp_settings() else ""


def is_configured() -> bool:
    return bool(provider())


async def _send_with_resend(message: ContactMessage, recipient: str) -> None:
    payload = {
        "from": sender_address(),
        "to": [recipient],
        "reply_to": f"{message.name} <{message.email}>",
        "subject": message.mail_subject(),
        "text": message.body(),
    }
    async with httpx.AsyncClient(timeout=SEND_TIMEOUT) as client:
        response = await client.post(
            RESEND_ENDPOINT,
            json=payload,
            headers={"Authorization": f"Bearer {_resend_key()}", "Content-Type": "application/json"},
        )
    if response.status_code >= 400:
        # Resend explains refusals in the body (an unverified sending domain, most often).
        logger.error("Resend refused the message (%s): %s", response.status_code, response.text[:300])
        raise ContactError(f"The mail provider refused the message ({response.status_code}).")

    # Resend's id is how a message is traced in its dashboard when a recipient says nothing arrived.
    try:
        message_id = (response.json() or {}).get("id", "")
    except ValueError:
        message_id = ""
    if message_id:
        logger.info("Resend accepted the message as %s", message_id)


def _send_with_smtp_blocking(message: ContactMessage, recipient: str, smtp: dict[str, object]) -> None:
    mail = EmailMessage()
    mail["From"] = sender_address()
    mail["To"] = recipient
    mail["Reply-To"] = f"{message.name} <{message.email}>"
    mail["Subject"] = message.mail_subject()
    mail.set_content(message.body())

    host, port = str(smtp["host"]), int(smtp["port"])
    if smtp["starttls"]:
        with smtplib.SMTP(host, port, timeout=SEND_TIMEOUT) as server:
            server.starttls()
            server.login(str(smtp["username"]), str(smtp["password"]))
            server.send_message(mail)
    else:
        with smtplib.SMTP_SSL(host, port, timeout=SEND_TIMEOUT) as server:
            server.login(str(smtp["username"]), str(smtp["password"]))
            server.send_message(mail)


async def forward(message: ContactMessage, recipient: str = "") -> str:
    """Send one checked message to the EKIOBA inbox. Returns the provider that carried it.

    Raises ContactNotConfigured when no provider is set up, and ContactError when one is but
    the send failed.
    """
    recipient = (recipient or FORWARD_TO).strip()
    if not recipient:
        raise ContactNotConfigured("No forwarding address is configured.")

    chosen = provider()
    if chosen == "resend":
        await _send_with_resend(message, recipient)
        return "resend"
    if chosen == "smtp":
        smtp = _smtp_settings()
        assert smtp is not None  # provider() only says "smtp" when the settings are complete
        try:
            await asyncio.to_thread(_send_with_smtp_blocking, message, recipient, smtp)
        except smtplib.SMTPAuthenticationError as exc:
            logger.error("SMTP rejected the credentials: %s", exc)
            raise ContactError("The mail server refused our credentials.") from exc
        except (smtplib.SMTPException, OSError) as exc:
            logger.error("SMTP send failed: %r", exc)
            raise ContactError("The mail server could not be reached.") from exc
        return "smtp"

    raise ContactNotConfigured("No mail provider is configured.")


async def submit(message: ContactMessage, recipient: str = "") -> str:
    """Forward a message, and make sure it survives even when forwarding fails.

    A visitor who took the trouble to write should not lose their message to a missing API key,
    so anything that can't be sent is written to the log, where the operator can still find it.
    """
    try:
        return await forward(message, recipient)
    except ContactError:
        logger.error(
            "Contact form message could not be sent, so it is recorded here:\n"
            "Subject: %s\nFrom: %s <%s>\n%s",
            message.subject, message.name, message.email, message.message,
        )
        raise
