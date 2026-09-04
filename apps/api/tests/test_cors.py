"""Tests for the minimal CORS configuration used by the web app."""

from fastapi.testclient import TestClient

from app.main import app


def test_cors_preflight_allows_localhost_3000() -> None:
    client = TestClient(app)
    response = client.options(
        "/api/researches",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "http://localhost:3000"
    )
    assert "POST" in response.headers["access-control-allow-methods"]


def test_cors_preflight_rejects_unknown_origin() -> None:
    client = TestClient(app)
    response = client.options(
        "/api/researches",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    # Starlette rejects preflights from origins that are not allowed.
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
