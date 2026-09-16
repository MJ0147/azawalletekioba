import hashlib
import hmac
import importlib.util
import time
from pathlib import Path
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from services import admin_routes, telegram_login

FRONTEND_DIR = Path(__file__).resolve().parents[1]
BOT_TOKEN = "123456:TEST-bot-token"


@pytest.fixture(scope="module")
def frontend():
    spec = importlib.util.spec_from_file_location("ekioba_frontend_app_telegram", FRONTEND_DIR / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def client(frontend, tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("ACADEMY_SESSION_SECRET", "test-session-secret-0123456789abcdef")
    monkeypatch.setenv("ACADEMY_DATABASE_URL", f"sqlite:///{(tmp_path / 'academy.db').as_posix()}")
    for variable in ("TELEGRAM_ADMIN_USERNAMES", "TELEGRAM_ADMIN_IDS", "ACADEMY_ADMIN_TOKEN", "ORDERS_ADMIN_TOKEN", "PUBLIC_BASE_URL"):
        monkeypatch.delenv(variable, raising=False)
    return TestClient(frontend.app, follow_redirects=False)


def telegram_login_data(**fields):
    """Login data signed the way Telegram signs it for this bot."""
    data = {"id": "777", "first_name": "Aza", "username": "Azavault", "auth_date": str(int(time.time())), **fields}
    check_string = "\n".join(f"{key}={data[key]}" for key in sorted(data))
    data["hash"] = hmac.new(hashlib.sha256(BOT_TOKEN.encode()).digest(), check_string.encode(), hashlib.sha256).hexdigest()
    return data


def log_in(client, **fields):
    response = client.get("/auth/telegram/callback?" + urlencode({"next": "/admin", **telegram_login_data(**fields)}))
    assert response.status_code == 303, response.text
    return response


def test_only_genuine_fresh_telegram_logins_are_accepted():
    user = telegram_login.verify_login({**telegram_login_data(), "next": "/admin"}, BOT_TOKEN)  # our own params aren't signed
    assert (user.id, user.username) == (777, "Azavault")

    tampered = {**telegram_login_data(), "username": "Ramseyaimua"}
    expired = telegram_login_data(auth_date=str(int(time.time()) - 2 * 86400))
    unsigned = {key: value for key, value in telegram_login_data().items() if key != "hash"}
    for bad in (tampered, expired, unsigned):
        with pytest.raises(telegram_login.TelegramLoginError):
            telegram_login.verify_login(bad, BOT_TOKEN)
    with pytest.raises(telegram_login.TelegramLoginError):
        telegram_login.verify_login(telegram_login_data(), "another-bot-token")


def test_logging_in_sets_a_session_and_returns_to_a_page_on_this_site(client):
    response = log_in(client)
    assert response.headers["location"] == "/admin"
    assert client.get("/api/telegram/me").json() == {"signed_in": True, "id": 777, "username": "Azavault", "is_admin": True}

    elsewhere = client.get("/auth/telegram/callback?" + urlencode({"next": "https://evil.example", **telegram_login_data()}))
    assert elsewhere.headers["location"] == "/"
    forged = client.get("/auth/telegram/callback?" + urlencode({**telegram_login_data(), "username": "Ramseyaimua"}))
    assert forged.headers["location"].startswith("/login?") and "error=" in forged.headers["location"]

    client.post("/api/telegram/logout")
    client.cookies.clear()
    assert client.get("/api/telegram/me").json() == {"signed_in": False, "is_admin": False}


def test_azavault_and_ramseyaimua_are_admins_and_ids_can_be_added(monkeypatch):
    User = telegram_login.TelegramUser
    assert telegram_login.is_admin(User(1, "Azavault")) and telegram_login.is_admin(User(2, "ramseyaimua"))
    assert not telegram_login.is_admin(User(3, "someone_else")) and not telegram_login.is_admin(User(4, ""))
    monkeypatch.setenv("TELEGRAM_ADMIN_IDS", "4, 5")
    assert telegram_login.is_admin(User(4, "")) and telegram_login.is_admin(User(5, "anyone"))


def test_telegram_admins_have_every_admin_right(client, monkeypatch):
    admin_apis = ["/api/academy/admin/conversions", "/api/orders", "/api/admin/knowledge-suggestions"]

    # A developer's own .env would otherwise decide what these assertions see.
    for leaked in ("IYOBO_ADMIN_TOKEN", "AI_ASSISTANT_URL", "NEXT_PUBLIC_IYOBO_API_URL", "VERCEL"):
        monkeypatch.delenv(leaked, raising=False)

    log_in(client, id="999", username="not_an_admin")
    assert [client.get(path).status_code for path in admin_apis] == [401, 401, 401]
    assert "isn't an EKIOBA admin" in client.get("/admin").text

    client.cookies.clear()
    log_in(client, id="888", username="Ramseyaimua")
    assert client.get("/api/academy/admin/conversions").json() == {"conversions": []}
    assert client.get("/api/orders").status_code == 200
    assert "adminHub()" in client.get("/admin").text

    assert client.get("/api/admin/knowledge-suggestions").status_code == 503  # needs IYOBO_ADMIN_TOKEN
    monkeypatch.setenv("IYOBO_ADMIN_TOKEN", "iyobo-admin-token")
    calls = []

    async def fake_send(method, url, token, *, params=None, body=None):
        calls.append((method, url, token, params, body))
        return 200, {"suggestion": {"id": 3, "status": "approved"}}

    monkeypatch.setattr(admin_routes, "send_to_assistant", fake_send)
    approved = client.post("/api/admin/knowledge-suggestions/3/approve", json={"note": "Correct"})
    assert approved.json()["suggestion"]["status"] == "approved"
    assert calls == [("POST", "http://localhost:8005/admin/knowledge-suggestions/3/approve", "iyobo-admin-token", None, {"note": "Correct"})]


def test_login_page_embeds_the_telegram_widget_for_idiacoinbot(client):
    page = client.get("/login?next=/academy").text
    assert 'src="https://telegram.org/js/telegram-widget.js?22"' in page
    assert 'data-telegram-login="IdiacoinBot"' in page
    assert 'data-auth-url="http://testserver/auth/telegram/callback?next=/academy"' in page
    assert 'id="account-link"' in client.get("/museum").text  # the header links to it on every page


@pytest.mark.parametrize("admin_id", ["8894431525", "7152238199"])
def test_the_named_admins_are_recognised_by_telegram_id_alone(client, admin_id):
    """@Azavault and @Ramseyaimua stay admins even if their username changes or is hidden."""
    log_in(client, id=admin_id, username="")
    assert client.get("/api/orders").status_code == 200
    assert "adminHub()" in client.get("/admin").text


def test_an_unlisted_telegram_id_is_not_an_admin(client):
    log_in(client, id="8894431524", username="")
    assert client.get("/api/orders").status_code == 401
