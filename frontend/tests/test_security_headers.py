"""Headers every response carries, and the root-file route's containment."""

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FRONTEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def client():
    spec = importlib.util.spec_from_file_location("ekioba_frontend_app_headers", FRONTEND_DIR / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return TestClient(module.app)


def test_pages_carry_the_security_headers(client):
    headers = client.get("/museum").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "frame-ancestors" in headers["Content-Security-Policy"]


def test_telegram_may_still_frame_the_site(client):
    """A Mini App runs in an iframe on Telegram Web, so framing must not be denied outright."""
    policy = client.get("/").headers["Content-Security-Policy"]
    assert "https://web.telegram.org" in policy
    assert "frame-ancestors 'none'" not in policy
    assert "X-Frame-Options" not in client.get("/").headers


def test_the_root_file_route_stays_inside_public(client):
    for probe in ("..%2Fapp.py", "..%2F..%2F.env", "%2e%2e%2fapp.py", "....//app.py", "app.py", ".env"):
        response = client.get("/" + probe)
        assert response.status_code == 404, probe
        assert "SECRET" not in response.text.upper(), probe
