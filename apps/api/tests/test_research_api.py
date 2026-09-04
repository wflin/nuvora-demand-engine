"""Real-PostgreSQL CRUD tests for the Research API.

Every request runs through the real FastAPI app and the real PostgreSQL
database. Test data is isolated inside a savepoint-backed transaction and
rolled back after each test, so the development database stays clean.
"""

import time
import uuid
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ResearchProject

API_PREFIX = "/api/researches"


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def create_payload(**overrides: str) -> dict[str, str]:
    payload = {
        "name": "Invoice software research",
        "seed_keyword": "invoice",
    }
    payload.update(overrides)
    return payload


def create_research(client: TestClient, **overrides: str) -> dict[str, str]:
    response = client.post(API_PREFIX, json=create_payload(**overrides))
    assert response.status_code == 201
    return response.json()


def test_create_research_minimal(client: TestClient) -> None:
    response = client.post(API_PREFIX, json=create_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Invoice software research"
    assert body["seed_keyword"] == "invoice"
    assert body["description"] is None
    assert body["country_code"] == "US"
    assert body["language_code"] == "en"
    assert body["status"] == "draft"
    assert uuid.UUID(body["id"])
    assert body["created_at"]
    assert body["updated_at"]


def test_create_research_with_all_fields(client: TestClient) -> None:
    payload = create_payload(
        name="Resume builder research",
        seed_keyword="resume builder",
        description="English resume builder demand",
        country_code="GB",
        language_code="en",
        status="running",
    )
    response = client.post(API_PREFIX, json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Resume builder research"
    assert body["seed_keyword"] == "resume builder"
    assert body["description"] == "English resume builder demand"
    assert body["country_code"] == "GB"
    assert body["language_code"] == "en"
    assert body["status"] == "running"


def test_list_researches_returns_items_newest_first(client: TestClient) -> None:
    first = create_research(client, name="First", seed_keyword="pdf converter")
    time.sleep(0.01)
    second = create_research(client, name="Second", seed_keyword="qr code")

    response = client.get(API_PREFIX)
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    ids = [item["id"] for item in body["items"]]
    assert ids == [second["id"], first["id"]]


def test_get_research_returns_fields(client: TestClient) -> None:
    created = create_research(client, name="Image compressor", seed_keyword="image compressor")
    response = client.get(f"{API_PREFIX}/{created['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["name"] == "Image compressor"
    assert body["seed_keyword"] == "image compressor"
    assert body["status"] == "draft"


def test_get_research_not_found_returns_404(client: TestClient) -> None:
    response = client.get(f"{API_PREFIX}/{uuid.uuid4()}")
    assert response.status_code == 404


def test_patch_research_updates_fields(client: TestClient) -> None:
    created = create_research(client)
    before = parse_datetime(created["updated_at"])
    time.sleep(0.01)

    response = client.patch(
        f"{API_PREFIX}/{created['id']}",
        json={
            "name": "Renamed research",
            "description": "Updated description",
            "status": "running",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed research"
    assert body["description"] == "Updated description"
    assert body["status"] == "running"
    assert body["seed_keyword"] == created["seed_keyword"]
    assert parse_datetime(body["updated_at"]) > before


def test_patch_research_not_found_returns_404(client: TestClient) -> None:
    response = client.patch(f"{API_PREFIX}/{uuid.uuid4()}", json={"name": "x"})
    assert response.status_code == 404


def test_delete_research_removes_row(client: TestClient, db: Session) -> None:
    created = create_research(client)
    research_id = uuid.UUID(created["id"])

    response = client.delete(f"{API_PREFIX}/{research_id}")
    assert response.status_code == 204
    assert response.content == b""

    assert db.get(ResearchProject, research_id) is None
    assert client.get(f"{API_PREFIX}/{research_id}").status_code == 404


def test_delete_research_not_found_returns_404(client: TestClient) -> None:
    response = client.delete(f"{API_PREFIX}/{uuid.uuid4()}")
    assert response.status_code == 404


def test_created_research_is_queryable_in_postgres(
    client: TestClient,
    db: Session,
) -> None:
    created = create_research(client)
    research_id = uuid.UUID(created["id"])

    stored = db.get(ResearchProject, research_id)
    assert stored is not None
    assert stored.name == "Invoice software research"
    assert stored.seed_keyword == "invoice"
    assert stored.country_code == "US"
    assert stored.language_code == "en"
    assert stored.status == "draft"
    assert stored.created_at is not None
    assert stored.updated_at is not None


def transition_research(
    client: TestClient,
    research_id: str,
    *statuses: str,
) -> None:
    """Move a research through a chain of legal status transitions."""
    for target in statuses:
        response = client.patch(
            f"{API_PREFIX}/{research_id}",
            json={"status": target},
        )
        assert response.status_code == 200
        assert response.json()["status"] == target


def test_patch_status_legal_transition_returns_200(client: TestClient) -> None:
    created = create_research(client)
    response = client.patch(
        f"{API_PREFIX}/{created['id']}",
        json={"status": "running"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_patch_status_illegal_transition_returns_409_and_preserves_state(
    client: TestClient,
    db: Session,
) -> None:
    created = create_research(client)
    research_id = uuid.UUID(created["id"])

    response = client.patch(
        f"{API_PREFIX}/{research_id}",
        json={"status": "completed"},
    )
    assert response.status_code == 409

    stored = db.get(ResearchProject, research_id)
    assert stored is not None
    assert stored.status == "draft"


def test_patch_status_invalid_value_returns_422(client: TestClient) -> None:
    created = create_research(client)
    response = client.patch(
        f"{API_PREFIX}/{created['id']}",
        json={"status": "bogus"},
    )
    assert response.status_code == 422


def test_patch_status_same_value_is_noop(
    client: TestClient,
    db: Session,
) -> None:
    created = create_research(client)
    research_id = uuid.UUID(created["id"])

    response = client.patch(
        f"{API_PREFIX}/{research_id}",
        json={"status": "draft"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "draft"
    assert body["updated_at"] == created["updated_at"]
    assert db.get(ResearchProject, research_id).status == "draft"


def test_patch_status_updates_updated_at(client: TestClient) -> None:
    created = create_research(client)
    before = parse_datetime(created["updated_at"])
    time.sleep(0.01)

    response = client.patch(
        f"{API_PREFIX}/{created['id']}",
        json={"status": "running"},
    )
    assert response.status_code == 200
    assert parse_datetime(response.json()["updated_at"]) > before


def test_full_legal_transition_chain(client: TestClient) -> None:
    created = create_research(client)
    transition_research(client, created["id"], "running", "completed")

    body = client.get(f"{API_PREFIX}/{created['id']}").json()
    assert body["status"] == "completed"


def test_terminal_states_are_terminal(client: TestClient) -> None:
    terminal_cases = [
        ("completed", "running"),
        ("failed", "completed"),
        ("cancelled", "draft"),
    ]
    for terminal_status, forbidden_target in terminal_cases:
        created = create_research(client)
        transition_research(client, created["id"], "running", terminal_status)

        response = client.patch(
            f"{API_PREFIX}/{created['id']}",
            json={"status": forbidden_target},
        )
        assert response.status_code == 409

        body = client.get(f"{API_PREFIX}/{created['id']}").json()
        assert body["status"] == terminal_status
