"""Tests for the health endpoint."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_app_can_be_loaded_by_test_client() -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_json() -> None:
    response = client.get("/health")
    assert response.headers["content-type"].startswith("application/json")


def test_health_returns_status_ok() -> None:
    response = client.get("/health")
    assert response.json() == {"status": "ok"}
