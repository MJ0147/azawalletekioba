import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "local-test-secret")

from app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_root(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Iyobo AI Assistant"
    assert data["status"] == "running"


def test_ready(client) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_health(client) -> None:
    response = client.get("/health")
    assert response.status_code in (200, 503)
    data = response.json()
    if response.status_code == 200:
        assert data["status"] == "ok"
        assert data["database"] == "connected"
    else:
        assert data["detail"] == "Database connection failed"
