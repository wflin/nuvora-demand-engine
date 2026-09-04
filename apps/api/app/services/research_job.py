"""Research Job status state machine and lifecycle operations.

The ResearchJob lifecycle is a separate concept from the ResearchProject
lifecycle (ResearchStatus); each has its own centralized state machine.
"""

import logging
from collections.abc import Callable
from enum import StrEnum
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models import ResearchJob, ResearchProject
from app.services.research import (
    ResearchStatus,
    validate_transition as validate_research_transition,
)

logger = logging.getLogger(__name__)

RUN_FAILED_MESSAGE = "Research job execution failed"


class ResearchJobStatus(StrEnum):
    """Formal lifecycle states of a research job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


ALLOWED_TRANSITIONS: dict[ResearchJobStatus, set[ResearchJobStatus]] = {
    ResearchJobStatus.PENDING: {
        ResearchJobStatus.RUNNING,
        ResearchJobStatus.CANCELLED,
    },
    ResearchJobStatus.RUNNING: {
        ResearchJobStatus.COMPLETED,
        ResearchJobStatus.FAILED,
        ResearchJobStatus.CANCELLED,
    },
    ResearchJobStatus.COMPLETED: set(),
    ResearchJobStatus.FAILED: set(),
    ResearchJobStatus.CANCELLED: set(),
}

# Same-status transitions are accepted as no-ops for non-terminal states.
NOOP_STATUSES = frozenset({ResearchJobStatus.PENDING, ResearchJobStatus.RUNNING})

TERMINAL_STATES: frozenset[ResearchJobStatus] = frozenset(
    state for state, targets in ALLOWED_TRANSITIONS.items() if not targets
)


class InvalidJobStatusTransition(ValueError):
    """Raised when a research job status transition is not allowed."""


class ResearchNotFound(LookupError):
    """Raised when a research project does not exist."""


class ResearchNotRunnable(ValueError):
    """Raised when a research project cannot be started from its status."""


def can_transition(
    current: ResearchJobStatus | str,
    target: ResearchJobStatus,
) -> bool:
    """Return whether moving from ``current`` to ``target`` is allowed."""
    current_status = _coerce(current)
    if target == current_status:
        return current_status in NOOP_STATUSES
    return target in ALLOWED_TRANSITIONS[current_status]


def validate_transition(
    current: ResearchJobStatus | str,
    target: ResearchJobStatus,
) -> None:
    """Raise InvalidJobStatusTransition when the transition is not allowed."""
    if not can_transition(current, target):
        raise InvalidJobStatusTransition(
            f"Cannot transition research job status from "
            f"{_coerce(current).value} to {target.value}"
        )


def _coerce(value: ResearchJobStatus | str) -> ResearchJobStatus:
    if isinstance(value, ResearchJobStatus):
        return value
    return ResearchJobStatus(value)


def create_job(db: Session, research_id: UUID) -> ResearchJob:
    """Create a pending research job."""
    job = ResearchJob(research_id=research_id)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, job_id: UUID) -> ResearchJob | None:
    """Return a research job by id, or None when missing."""
    return db.get(ResearchJob, job_id)


def start_job(db: Session, job: ResearchJob) -> ResearchJob:
    """Start a pending job (pending -> running)."""
    _mark(job, ResearchJobStatus.RUNNING, started=True)
    db.commit()
    db.refresh(job)
    return job


def complete_job(db: Session, job: ResearchJob) -> ResearchJob:
    """Complete a running job (running -> completed)."""
    _mark(job, ResearchJobStatus.COMPLETED, finished=True)
    db.commit()
    db.refresh(job)
    return job


def fail_job(
    db: Session,
    job: ResearchJob,
    error_message: str | None = None,
) -> ResearchJob:
    """Fail a running job (running -> failed) with a safe error message."""
    _mark(
        job,
        ResearchJobStatus.FAILED,
        finished=True,
        error_message=error_message,
    )
    db.commit()
    db.refresh(job)
    return job


def cancel_job(db: Session, job: ResearchJob) -> ResearchJob:
    """Cancel a pending or running job (-> cancelled)."""
    _mark(job, ResearchJobStatus.CANCELLED, finished=True)
    db.commit()
    db.refresh(job)
    return job


def _mark(
    job: ResearchJob,
    target: ResearchJobStatus,
    *,
    started: bool = False,
    finished: bool = False,
    error_message: str | None = None,
) -> None:
    validate_transition(job.status, target)
    job.status = target.value
    if started:
        job.started_at = utcnow()
    if finished:
        job.finished_at = utcnow()
    if error_message is not None:
        job.error_message = error_message


def run_research(
    db: Session,
    research_id: UUID,
    work: Callable[[], None] | None = None,
) -> ResearchJob:
    """Run a research synchronously and return its finished job.

    The research must be in ``draft``. The job is created (pending), started
    (running), the research moves to ``running``, the skeleton work runs, and
    on success both the job and the research end in ``completed``. On failure
    both end in ``failed`` with a safe error message. No keyword data is
    fetched or fabricated.
    """
    research = db.get(ResearchProject, research_id)
    if research is None:
        raise ResearchNotFound(f"Research {research_id} not found")
    if research.status != ResearchStatus.DRAFT.value:
        raise ResearchNotRunnable(
            f"Research {research_id} cannot be run from status {research.status}"
        )

    job = ResearchJob(
        research_id=research.id,
        status=ResearchJobStatus.PENDING.value,
    )
    db.add(job)
    _mark(job, ResearchJobStatus.RUNNING, started=True)
    validate_research_transition(research.status, ResearchStatus.RUNNING)
    research.status = ResearchStatus.RUNNING.value
    db.flush()

    try:
        _run_skeleton_work(work)
        _mark(job, ResearchJobStatus.COMPLETED, finished=True)
        validate_research_transition(research.status, ResearchStatus.COMPLETED)
        research.status = ResearchStatus.COMPLETED.value
        db.commit()
    except Exception:
        _mark(
            job,
            ResearchJobStatus.FAILED,
            finished=True,
            error_message=RUN_FAILED_MESSAGE,
        )
        if research.status != ResearchStatus.COMPLETED.value:
            research.status = ResearchStatus.FAILED.value
        db.commit()
        raise

    db.refresh(job)
    return job


def _run_skeleton_work(work: Callable[[], None] | None) -> None:
    if work is None:
        logger.info("Research job skeleton executed: no provider data available yet")
        return
    work()
