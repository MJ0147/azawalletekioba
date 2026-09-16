import importlib.util
import struct
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FRONTEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def client():
    spec = importlib.util.spec_from_file_location("ekioba_frontend_app_pwa", FRONTEND_DIR / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return TestClient(module.app)


def _png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    return struct.unpack(">II", data[16:24])


def test_manifest_makes_the_site_installable(client):
    response = client.get("/manifest.webmanifest")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/manifest+json")
    manifest = response.json()
    assert manifest["display"] == "standalone"
    assert manifest["start_url"].startswith("/") and manifest["short_name"] == "EKIOBA"

    sizes_by_purpose: dict[str, set[str]] = {}
    for icon in manifest["icons"]:
        image = client.get(icon["src"])
        assert image.status_code == 200, icon["src"]
        width, height = _png_size(image.content)
        assert f"{width}x{height}" == icon["sizes"], icon["src"]
        sizes_by_purpose.setdefault(icon["purpose"], set()).add(icon["sizes"])
    assert {"192x192", "512x512"} <= sizes_by_purpose["any"]
    assert "512x512" in sizes_by_purpose["maskable"]


def test_service_worker_is_served_from_the_site_root(client):
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert "addEventListener('fetch'" in response.text


def test_every_page_links_the_manifest_but_only_the_homepage_offers_to_install(client):
    museum = client.get("/museum").text
    assert '<link rel="manifest" href="/manifest.webmanifest" />' in museum
    assert "navigator.serviceWorker.register('/sw.js')" in museum
    assert 'id="install-prompt"' not in museum

    home = client.get("/").text
    assert 'id="install-prompt"' in home
    assert "Add to Home Screen" in home


def test_header_wallet_button_opens_ton_connect_directly(client):
    page = client.get("/museum").text
    start = page.index("window.openWalletConnect = async function")
    handler = page[start : page.index("window.connectTonkeeper = async function", start)]
    assert handler.index("ui.openModal()") < handler.index("idia-modal")  # the wallet picker comes first
