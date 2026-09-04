"""Real-PostgreSQL tests for the ResearchJob model, service, and APIs."""

import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Keyword,
    KeywordMetricSnapshot,
    ResearchJob,
    ResearchKeyword,
    ResearchProject,
)
from app.services.research_job import (
    InvalidJobStatusTransition,
    ResearchJobStatus,
    ResearchNotFound,
    ResearchNotRunnable,
    can_transition,
    cancel_job,
    complete_job,
    create_job,
    fail_job,
    get_job,
    run_research,
    start_job,
    validate_transition,
)

API_PREFIX = "/api/researches"

LEGAL_TRANSITIONS = [
    (ResearchJobStatus.PENDING, ResearchJobStatus.RUNNING),
    (ResearchJobStatus.PENDING, ResearchJobStatus.CANCELLED),
    (ResearchJobStatus.RUNNING, ResearchJobStatus.COMPLETED),
    (ResearchJobStatus.RUNNING, ResearchJobStatus.FAILED),
    (ResearchJobStatus.RUNNING, ResearchJobStatus.CANCELLED),
]

ILLEGAL_TRANSITIONS = [
    (ResearchJobStatus.PENDING, ResearchJobStatus.COMPLETED),
    (ResearchJobStatus.PENDING, ResearchJobStatus.FAILED),
    (ResearchJobStatus.RUNNING, ResearchJobStatus.PENDING),
    (ResearchJobStatus.COMPLETED, ResearchJobStatus.RUNNING),
    (ResearchJobStatus.COMPLETED, ResearchJobStatus.PENDING),
    (ResearchJobStatus.COMPLETED, ResearchJobStatus.FAILED),
    (ResearchJobStatus.COMPLETED, ResearchJobStatus.CANCELLED),
    (ResearchJobStatus.FAILED, ResearchJobStatus.RUNNING),
    (ResearchJobStatus.FAILED, ResearchJobStatus.COMPLETED),
    (ResearchJobStatus.FAILED, ResearchJobStatus.PENDING),
    (ResearchJobStatus.FAILED, ResearchJobStatus.CANCELLED),
    (ResearchJobStatus.CANCELLED, ResearchJobStatus.RUNNING),
    (ResearchJobStatus.CANCELLED, ResearchJobStatus.PENDING),
    (ResearchJobStatus.CANCELLED, ResearchJobStatus.COMPLETED),
    (ResearchJobStatus.CANCELLED, ResearchJobStatus.FAILED),
]


def make_research(db: Session, **overrides: str) -> ResearchProject:
    values = {
        "name": "Job research",
        "seed_keyword": "invoice",
        "country_code": "US",
        "language_code": "en",
        "status": "draft",
    }
    values.update(overrides)
    research = ResearchProject(**values)
    db.add(research)
    db.flush()
    return research


def create_research_via_api(client: TestClient) -> dict[str, str]:
    response = client.post(
        API_PREFIX,
        json={"name": "Job research", "seed_keyword": "invoice"},
    )
    assert response.status_code == 201
    return response.json()


def transition_research(
    client: TestClient,
    research_id: str,
    *statuses: str,
) -> None:
    for target in statuses:
        response = client.patch(
            f"{API_PREFIX}/{research_id}",
            json={"status": target},
        )
        assert response.status_code == 200
        assert response.json()["status"] == target


def test_job_status_values() -> None:
    assert [state.value for state in ResearchJobStatus] == [
        "pending",
        "running",
        "completed",
        "failed",
        "cancelled",
    ]


@pytest.mark.parametrize(("current", "target"), LEGAL_TRANSITIONS)
def test_legal_job_transitions_are_allowed(
    current: ResearchJobStatus,
    target: ResearchJobStatus,
) -> None:
    assert can_transition(current, target) is True
    validate_transition(current, target)


@pytest.mark.parametrize(("current", "target"), ILLEGAL_TRANSITIONS)
def test_illegal_job_transitions_are_rejected(
    current: ResearchJobStatus,
    target: ResearchJobStatus,
) -> None:
    assert can_transition(current, target) is False
    with pytest.raises(InvalidJobStatusTransition):
        validate_transition(current, target)


def test_same_status_noop_for_pending_and_running() -> None:
    for state in (ResearchJobStatus.PENDING, ResearchJobStatus.RUNNING):
        assert can_transition(state, state) is True
        validate_transition(state, state)


def test_terminal_same_status_is_rejected() -> None:
    for state in (
        ResearchJobStatus.COMPLETED,
        ResearchJobStatus.FAILED,
        ResearchJobStatus.CANCELLED,
    ):
        assert can_transition(state, state) is False
        with pytest.raises(InvalidJobStatusTransition):
            validate_transition(state, state)


def test_create_job_defaults_to_pending(db: Session) -> None:
    research = make_research(db)
    job = create_job(db, research.id)
    assert job.research_id == research.id
    assert job.status == "pending"
    assert job.started_at is None
    assert job.finished_at is None
    assert job.error_message is None
    assert job.created_at.tzinfo is not None
    assert job.updated_at.tzinfo is not None


def test_start_job_moves_to_running(db: Session) -> None:
    research = make_research(db)
    job = create_job(db, research.id)
    start_job(db, job)
    assert job.status == "running"
    assert job.started_at is not None
    assert job.started_at.tzinfo is not None


def test_complete_job(db: Session) -> None:
    research = make_research(db)
    job = create_job(db, research.id)
    start_job(db, job)
    complete_job(db, job)
    assert job.status == "completed"
    assert job.finished_at is not None
    assert job.finished_at.tzinfo is not None


def test_fail_job(db: Session) -> None:
    research = make_research(db)
    job = create_job(db, research.id)
    start_job(db, job)
    fail_job(db, job, error_message="skeleton failed")
    assert job.status == "failed"
    assert job.finished_at is not None
    assert job.error_message == "skeleton failed"


def test_cancel_job_from_pending_and_running(db: Session) -> None:
    research = make_research(db)
    pending_job = create_job(db, research.id)
    cancel_job(db, pending_job)
    assert pending_job.status == "cancelled"

    running_job = create_job(db, research.id)
    start_job(db, running_job)
    cancel_job(db, running_job)
    assert running_job.status == "cancelled"


def test_job_illegal_transition_is_rejected(db: Session) -> None:
    research = make_research(db)
    job = create_job(db, research.id)
    with pytest.raises(InvalidJobStatusTransition):
        complete_job(db, job)
    assert job.status == "pending"


def test_job_terminal_states_cannot_transition(db: Session) -> None:
    research = make_research(db)
    job = create_job(db, research.id)
    start_job(db, job)
    complete_job(db, job)
    with pytest.raises(InvalidJobStatusTransition):
        start_job(db, job)
    with pytest.raises(InvalidJobStatusTransition):
        cancel_job(db, job)


def test_get_job_returns_none_for_missing(db: Session) -> None:
    assert get_job(db, uuid.uuid4()) is None


def test_job_foreign_key_requires_existing_research(db: Session) -> None:
    job = ResearchJob(research_id=uuid.uuid4())
    db.add(job)
    with pytest.raises(IntegrityError):
        db.flush()


def test_delete_research_cascades_jobs(db: Session) -> None:
    research = make_research(db)
    job = create_job(db, research.id)
    db.delete(research)
    db.commit()
    assert db.scalar(select(ResearchJob).where(ResearchJob.id == job.id)) is None


def test_run_research_success(db: Session) -> None:
    research = make_research(db)
    job = run_research(db, research.id)
    assert job.status == "completed"
    assert job.research_id == research.id
    assert job.started_at is not None
    assert job.finished_at is not None
    assert job.error_message is None
    stored = db.get(ResearchProject, research.id)
    assert stored.status == "completed"


def test_run_research_not_found(db: Session) -> None:
    with pytest.raises(ResearchNotFound):
        run_research(db, uuid.uuid4())


def test_run_research_not_runnable(db: Session) -> None:
    research = make_research(db, status="running")
    with pytest.raises(ResearchNotRunnable):
        run_research(db, research.id)


def test_run_research_failure_marks_both_failed(db: Session) -> None:
    research = make_research(db)

    def failing_work() -> None:
        raise RuntimeError("skeleton failure")

    with pytest.raises(RuntimeError):
        run_research(db, research.id, work=failing_work)

    stored = db.get(ResearchProject, research.id)
    assert stored.status == "failed"
    job = db.scalar(select(ResearchJob).where(ResearchJob.research_id == research.id))
    assert job is not None
    assert job.status == "failed"
    assert job.finished_at is not None
    assert job.error_message == "Research job execution failed"


def test_run_research_creates_no_keyword_data(
    client: TestClient,
    db: Session,
) -> None:
    research = create_research_via_api(client)
    response = client.post(f"{API_PREFIX}/{research['id']}/run")
    assert response.status_code == 200
    assert db.scalar(select(func.count()).select_from(Keyword)) == 0
    assert db.scalar(select(func.count()).select_from(ResearchKeyword)) == 0
    assert db.scalar(select(func.count()).select_from(KeywordMetricSnapshot)) == 0


def test_run_research_api_completes(client: TestClient) -> None:
    research = create_research_via_api(client)
    response = client.post(f"{API_PREFIX}/{research['id']}/run")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["research_id"] == research["id"]
    assert body["started_at"] is not None
    assert body["finished_at"] is not None
    assert body["error_message"] is None
    detail = client.get(f"{API_PREFIX}/{research['id']}").json()
    assert detail["status"] == "completed"


def test_run_research_api_not_found(client: TestClient) -> None:
    response = client.post(f"{API_PREFIX}/{uuid.uuid4()}/run")
    assert response.status_code == 404


@pytest.mark.parametrize(
    "chain",
    [
        ("running",),
        ("running", "completed"),
        ("running", "failed"),
        ("cancelled",),
    ],
)
def test_run_research_api_conflict_for_non_draft(
    client: TestClient,
    db: Session,
    chain: tuple[str, ...],
) -> None:
    research = create_research_via_api(client)
    transition_research(client, research["id"], *chain)

    response = client.post(f"{API_PREFIX}/{research['id']}/run")
    assert response.status_code == 409
    assert (
        db.scalar(
            select(func.count()).select_from(ResearchJob).where(
                ResearchJob.research_id == uuid.UUID(research["id"])
            )
        )
        == 0
    )
    body = client.get(f"{API_PREFIX}/{research['id']}").json()
    assert body["status"] == chain[-1]


def test_job_list_api_returns_jobs_newest_first(
    client: TestClient,
    db: Session,
) -> None:
    research = create_research_via_api(client)
    research_uuid = uuid.UUID(research["id"])
    first_job = create_job(db, research_uuid)
    time.sleep(0.01)
    second_job = create_job(db, research_uuid)

    response = client.get(f"{API_PREFIX}/{research['id']}/jobs")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert items[0]["id"] == str(second_job.id)
    assert items[1]["id"] == str(first_job.id)


def test_job_list_api_empty(client: TestClient) -> None:
    research = create_research_via_api(client)
    response = client.get(f"{API_PREFIX}/{research['id']}/jobs")
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_job_list_api_research_not_found(client: TestClient) -> None:
    response = client.get(f"{API_PREFIX}/{uuid.uuid4()}/jobs")
    assert response.status_code == 404


def test_job_detail_api(client: TestClient) -> None:
    research = create_research_via_api(client)
    job = client.post(f"{API_PREFIX}/{research['id']}/run").json()

    response = client.get(f"/api/research-jobs/{job['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == job["id"]
    assert body["research_id"] == research["id"]
    assert body["status"] == "completed"


def test_job_detail_api_not_found(client: TestClient) -> None:
    response = client.get(f"/api/research-jobs/{uuid.uuid4()}")
    assert response.status_code == 404
