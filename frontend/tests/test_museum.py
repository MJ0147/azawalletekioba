import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FRONTEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def frontend():
    # Load app.py by path: the frontend also has an app/ folder that `import app` could pick up.
    spec = importlib.util.spec_from_file_location("ekioba_frontend_app", FRONTEND_DIR / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def client(frontend):
    return TestClient(frontend.app)


def test_catalogue_lists_38_obas_in_reign_order(frontend):
    from services.museum import MUSEUM_PORTRAITS

    assert len(MUSEUM_PORTRAITS) == 38
    assert [p["number"] for p in MUSEUM_PORTRAITS] == list(range(1, 39))
    assert MUSEUM_PORTRAITS[0]["name"] == "Oba Eweka I"
    assert MUSEUM_PORTRAITS[-1]["name"] == "Oba Ewuare II"
    assert len({p["slug"] for p in MUSEUM_PORTRAITS}) == 38


def test_every_portrait_has_an_image_and_an_era(frontend):
    from services.museum import MUSEUM_ERAS, MUSEUM_PORTRAITS, museum_catalogue

    era_ids = {era["id"] for era in MUSEUM_ERAS}
    for portrait in MUSEUM_PORTRAITS:
        assert (FRONTEND_DIR / "static" / "images" / "museum" / f"{portrait['slug']}.jpg").is_file()
        assert portrait["era"] in era_ids
    assert sum(len(era["portraits"]) for era in museum_catalogue()) == 38


def test_museum_page_shows_inscriptions(client):
    response = client.get("/museum")
    assert response.status_code == 200
    assert "Benin Royal Museum" in response.text
    assert "Oba Ezoti" in response.text
    assert "Reigned only 14 days; assassinated by poisoned arrow at coronation" in response.text
    assert 'src="/static/images/museum/oba-ewuare-the-great.jpg"' in response.text


def test_portrait_image_is_served(client):
    response = client.get("/static/images/museum/oba-eweka-i.jpg")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
