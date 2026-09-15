import pytest
from fastapi.testclient import TestClient

from app import main
from app.grok_client import GrokError, GrokReply
from config import settings

SECRET = "test-webhook-secret"


@pytest.fixture(scope="module")
def client():
    return TestClient(main.app)


@pytest.fixture
def telegram(monkeypatch):
    """Fake bot token and secret; replies are captured instead of sent to Telegram."""
    class Sent(list):
        user_ids: list

    sent = Sent()

    async def capture_send(chat_id, text):
        sent.append((chat_id, text))
        return True

    async def answer(message, link_results=None, user_id=None):
        answer.user_ids.append(user_id)
        return GrokReply(text=f"Answer to: {message}"), []

    answer.user_ids = []
    sent.user_ids = answer.user_ids  # lets tests check who the reply was generated for

    monkeypatch.setattr(main, "TELEGRAM_TOKEN", "000000:test-token")
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(main, "send_telegram_message", capture_send)
    monkeypatch.setattr(main, "ask_iyobo", answer)
    return sent


def _update(**message):
    return {"update_id": 1, "message": {"message_id": 1, "chat": {"id": 42}, **message}}


def _post(client, payload, secret=SECRET):
    headers = {"X-Telegram-Bot-Api-Secret-Token": secret} if secret is not None else {}
    return client.post("/telegram/webhook", json=payload, headers=headers)


def test_text_message_gets_an_answer(client, telegram):
    update = _update(text="What is dog in Edo?")
    update["message"]["from"] = {"id": 777, "is_bot": False}
    response = _post(client, update)
    assert response.status_code == 200
    assert telegram == [(42, "Answer to: What is dog in Edo?")]
    assert telegram.user_ids == ["telegram:777"]  # remembered per Telegram user


def test_requests_without_the_telegram_secret_are_refused(client, telegram):
    assert _post(client, _update(text="spam"), secret=None).status_code == 403
    assert _post(client, _update(text="spam"), secret="wrong").status_code == 403
    assert telegram == []


def test_webhook_refuses_updates_until_a_secret_is_configured(client, telegram, monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", "")
    assert _post(client, _update(text="hi")).status_code == 503
    assert telegram == []


def test_ai_outage_sends_an_apology(client, telegram, monkeypatch):
    async def outage(message, link_results=None, user_id=None):
        raise GrokError("simulated outage")

    monkeypatch.setattr(main, "ask_iyobo", outage)
    assert _post(client, _update(text="hello")).status_code == 200
    assert telegram == [(42, main.AI_UNAVAILABLE_REPLY)]


@pytest.mark.parametrize(
    "payload",
    [
        _update(sticker={"file_id": "abc"}),
        {"update_id": 2, "edited_message": {"message_id": 1, "chat": {"id": 42}, "text": "hi"}},
        {"update_id": 3, "message": {"message_id": 1, "text": "no chat"}},
        {"update_id": 4, "message": "not an object"},
        ["not", "an", "update"],
    ],
    ids=["sticker", "edited-message", "missing-chat", "message-not-object", "not-an-object"],
)
def test_updates_without_an_answerable_text_are_ignored(client, telegram, payload):
    response = _post(client, payload)
    assert response.status_code == 200
    assert telegram == []


def test_invalid_json_is_ignored(client, telegram):
    response = client.post(
        "/telegram/webhook",
        content=b"not json",
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET, "Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert telegram == []


def test_long_replies_are_split_to_fit_telegram():
    parts = main.split_telegram_message("x" * 5000)
    assert [len(part) for part in parts] == [4096, 904]

    paragraph = "word " * 700  # about 3,500 characters
    text = paragraph + "\n" + paragraph
    parts = main.split_telegram_message(text)
    assert len(parts) == 2
    assert all(len(part) <= main.TELEGRAM_MAX_MESSAGE_CHARS for part in parts)
    assert parts[0] == paragraph.rstrip()


def test_short_replies_are_sent_whole():
    assert main.split_telegram_message("Koyo!") == ["Koyo!"]
