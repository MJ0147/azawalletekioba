"""The hotels page: its data survives being rendered, and the listings are real places."""

import importlib.util
import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FRONTEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def client():
    spec = importlib.util.spec_from_file_location("ekioba_frontend_app_hotels", FRONTEND_DIR / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return TestClient(module.app)


class _VisibleText(HTMLParser):
    """The text a reader actually sees, with script and style contents left out."""

    def __init__(self):
        super().__init__()
        self.skipping = ""
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skipping = tag

    def handle_endtag(self, tag):
        if tag == self.skipping:
            self.skipping = ""

    def handle_data(self, data):
        if not self.skipping:
            self.chunks.append(data)

    @property
    def text(self):
        return " ".join(self.chunks)


def visible_text(html: str) -> str:
    parser = _VisibleText()
    parser.feed(html)
    return parser.text


def listings(html: str) -> list[dict]:
    payload = re.search(r'id="hotel-listings">(.*?)</script>', html, re.S)
    assert payload, "the page should carry its listings as JSON"
    return json.loads(payload.group(1))


def test_the_page_does_not_print_its_own_source(client):
    """A double quote in the embedded JSON used to close x-data, spilling the component onto the page."""
    text = visible_text(client.get("/hotels").text)
    for code in ("searchCity", "confirmBook", "filteredListings", "price_per_night", "JSON.stringify"):
        assert code not in text, f"{code} is showing on the page as text"


def test_benin_city_listings_are_real_hotels(client):
    benin = [h for h in listings(client.get("/hotels").text) if h["city"] == "Benin City"]
    titles = {h["title"] for h in benin}
    assert "Protea Hotel by Marriott Benin City Select Emotan" in titles
    assert "Golden Tulip Essential Benin City" in titles
    # Invented names that were being shown before.
    assert not any("Garki" in t or "Heritage Luxury" in t for t in titles)
    # Every listing needs a street address and a rate to be bookable.
    for hotel in benin:
        assert hotel.get("address"), hotel["title"]
        assert float(hotel["price_per_night"]) > 0, hotel["title"]
