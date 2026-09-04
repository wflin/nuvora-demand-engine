"""Tests for the readiness endpoint.

Requires the Docker PostgreSQL to be running and DATABASE_URL to be set
(see .env.example). The database-down scenario is verified manually via
the real PostgreSQL lifecycle (docker compose stop/start).
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ready_returns_200_when_database_is_available() -> None:
    response = client.get("/ready")
    assert response.status_code == 200


def test_ready_returns_ready_json() -> None:
    response = client.get("/ready")
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"status": "ready"}
