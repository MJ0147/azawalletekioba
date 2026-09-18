"""The Contact Us form: what it accepts, what it refuses, and where it sends.

No test sends real mail. Both providers are stubbed, and what is checked is the message that
would have gone out — its recipient, its Reply-To, and that a visitor's words survive a failure.
"""

import asyncio
import importlib.util
import smtplib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services import contact

FRONTEND_DIR = Path(__file__).resolve().parents[1]

GOOD = {
    "name": "Osaro Igbinedion",
    "email": "osaro@example.com",
    "subject": "Order EK-1042",
    "message": "My order has not arrived yet, could you please check on it?",
}


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    """Start every test with no provider configured and no remembered submissions."""
    for name in ("RESEND_API_KEY", "SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD",
                 "SMTP_PORT", "SMTP_STARTTLS", "CONTACT_FROM"):
        monkeypatch.delenv(name, raising=False)
    contact.reset_rate_limit()
    yield
    contact.reset_rate_limit()


@pytest.fixture(scope="module")
def frontend():
    spec = importlib.util.spec_from_file_location("ekioba_frontend_app_contact", FRONTEND_DIR / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── What the form accepts ───────────────────────────────────────────────────


def test_a_filled_in_form_is_accepted():
    message = contact.validate(**GOOD, honeypot="")
    assert message.name == "Osaro Igbinedion"
    assert message.email == "osaro@example.com"
    assert message.subject == "Order EK-1042"
    assert message.mail_subject() == "[EKIOBA] Order EK-1042"


def test_a_message_without_a_subject_still_has_one():
    assert contact.validate(**{**GOOD, "subject": ""}).subject == contact.DEFAULT_SUBJECT


@pytest.mark.parametrize(
    "field, value",
    [("name", "O"), ("name", "   "), ("email", "nope"), ("email", "who@example"), ("message", "too short")],
)
def test_an_unusable_field_is_refused(field, value):
    with pytest.raises(contact.ContactError):
        contact.validate(**{**GOOD, field: value})


def test_the_honeypot_catches_a_form_filling_bot():
    with pytest.raises(contact.ContactError):
        contact.validate(**GOOD, honeypot="http://spam.example")


def test_a_header_cannot_be_forged_through_the_form():
    """A newline in the subject would let a sender inject headers of their own."""
    message = contact.validate(**{**GOOD, "subject": "Hello\r\nBcc: victim@example.com"})
    assert "\n" not in message.subject and "\r" not in message.subject
    assert "Bcc" not in message.mail_subject() or "\n" not in message.mail_subject()


def test_the_body_carries_who_wrote_it_and_when():
    body = contact.validate(**GOOD).body()
    assert GOOD["message"] in body
    assert "Osaro Igbinedion <osaro@example.com>" in body
    assert "Contact Us form" in body


def test_one_visitor_cannot_flood_the_inbox():
    for _ in range(contact.RATE_LIMIT):
        assert contact.within_rate_limit("41.58.0.1") is True
    assert contact.within_rate_limit("41.58.0.1") is False
    assert contact.within_rate_limit("41.58.0.2") is True, "a different visitor is unaffected"


# ── Where it sends ──────────────────────────────────────────────────────────


def test_messages_go_to_the_ekioba_inbox_by_default():
    assert contact.FORWARD_TO == "adcredesolutions@gmail.com"


def test_the_provider_is_whichever_one_is_configured(monkeypatch):
    assert contact.provider() == "" and not contact.is_configured()

    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_USERNAME", "ekioba@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    assert contact.provider() == "smtp"

    # Resend wins when both are set: Vercel's runtime has no outbound SMTP.
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    assert contact.provider() == "resend"


def test_the_sender_is_the_mailbox_smtp_authenticated_as(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_USERNAME", "ekioba@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    assert contact.sender_address() == "EKIOBA Contact Form <ekioba@gmail.com>"

    monkeypatch.setenv("CONTACT_FROM", "EKIOBA <hello@ekioba.com>")
    assert contact.sender_address() == "EKIOBA <hello@ekioba.com>"


def test_resend_is_asked_to_reply_to_the_visitor(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    sent = {}

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"id": "b7e1f0c2-0000-4a00-9c00-000000000000"}

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json=None, headers=None):
            sent.update(url=url, payload=json, headers=headers)
            return Response()

    monkeypatch.setattr(contact.httpx, "AsyncClient", Client)
    carried_by = asyncio.run(contact.forward(contact.validate(**GOOD)))

    assert carried_by == "resend"
    assert sent["url"] == contact.RESEND_ENDPOINT
    assert sent["payload"]["to"] == ["adcredesolutions@gmail.com"]
    assert sent["payload"]["reply_to"] == "Osaro Igbinedion <osaro@example.com>"
    assert sent["payload"]["subject"] == "[EKIOBA] Order EK-1042"
    assert GOOD["message"] in sent["payload"]["text"]
    assert sent["headers"]["Authorization"] == "Bearer re_test"


def test_a_refusal_from_resend_is_reported_not_swallowed(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")

    class Response:
        status_code = 403
        text = '{"message": "You can only send testing emails to your own address."}'

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(contact.httpx, "AsyncClient", Client)
    with pytest.raises(contact.ContactError):
        asyncio.run(contact.forward(contact.validate(**GOOD)))


def test_smtp_sends_a_well_formed_mail(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_USERNAME", "ekioba@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    delivered = {}

    class Server:
        def __init__(self, host, port, timeout=None):
            delivered.update(host=host, port=port)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def login(self, username, password):
            delivered.update(username=username, password=password)

        def send_message(self, mail):
            delivered["mail"] = mail

    monkeypatch.setattr(smtplib, "SMTP_SSL", Server)
    assert asyncio.run(contact.forward(contact.validate(**GOOD))) == "smtp"

    mail = delivered["mail"]
    assert (delivered["host"], delivered["port"]) == ("smtp.gmail.com", 465)
    assert mail["To"] == "adcredesolutions@gmail.com"
    assert mail["Reply-To"] == "Osaro Igbinedion <osaro@example.com>"
    assert mail["From"] == "EKIOBA Contact Form <ekioba@gmail.com>"
    assert GOOD["message"] in mail.get_content()


def test_port_587_is_sent_over_starttls(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "ekioba@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "password")
    steps = []

    class Server:
        def __init__(self, host, port, timeout=None):
            steps.append(("connect", port))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            steps.append(("starttls", None))

        def login(self, *args):
            steps.append(("login", None))

        def send_message(self, mail):
            steps.append(("send", None))

    monkeypatch.setattr(smtplib, "SMTP", Server)
    asyncio.run(contact.forward(contact.validate(**GOOD)))
    assert steps == [("connect", 587), ("starttls", None), ("login", None), ("send", None)]


def test_an_unsendable_message_is_written_to_the_log(monkeypatch, caplog):
    """A visitor's words must not vanish because an API key is missing."""
    with caplog.at_level("ERROR"):
        with pytest.raises(contact.ContactNotConfigured):
            asyncio.run(contact.submit(contact.validate(**GOOD)))
    assert GOOD["message"] in caplog.text
    assert "osaro@example.com" in caplog.text


# ── The page ────────────────────────────────────────────────────────────────


def test_the_page_offers_the_form_and_the_address(frontend):
    page = TestClient(frontend.app).get("/contact")
    assert page.status_code == 200
    assert 'name="message"' in page.text
    assert "adcredesolutions@gmail.com" in page.text


def test_every_page_links_to_it(frontend):
    assert '/contact' in TestClient(frontend.app).get("/").text


def test_a_sent_message_is_confirmed_to_the_visitor(frontend, monkeypatch):
    forwarded = {}

    async def fake_submit(message, recipient=""):
        forwarded["message"] = message
        return "resend"

    monkeypatch.setattr(frontend.contact_service, "submit", fake_submit)
    response = TestClient(frontend.app).post("/contact", data=GOOD, headers={"HX-Request": "true"})

    assert response.status_code == 200
    assert "on its way" in response.text
    assert forwarded["message"].email == "osaro@example.com"


def test_a_visitor_is_given_the_address_when_the_form_cannot_send(frontend):
    """With no provider configured the message is undeliverable — say so, don't pretend."""
    response = TestClient(frontend.app).post("/contact", data=GOOD, headers={"HX-Request": "true"})
    assert "adcredesolutions@gmail.com" in response.text
    assert "on its way" not in response.text


def test_a_rejected_form_comes_back_with_what_was_typed(frontend):
    response = TestClient(frontend.app).post("/contact", data={**GOOD, "email": "nope"})
    assert "email address we can reply to" in response.text
    assert 'value="Osaro Igbinedion"' in response.text, "the visitor should not have to retype it"


def test_the_honeypot_is_refused_by_the_route(frontend):
    response = TestClient(frontend.app).post(
        "/contact", data={**GOOD, "website": "http://spam.example"}, headers={"HX-Request": "true"}
    )
    assert "on its way" not in response.text
