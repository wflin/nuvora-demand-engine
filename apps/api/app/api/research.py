"""Research CRUD API routes."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models import ResearchJob, ResearchProject
from app.schemas.research import (
    ResearchCreate,
    ResearchListResponse,
    ResearchResponse,
    ResearchUpdate,
)
from app.schemas.research_job import ResearchJobListResponse, ResearchJobResponse
from app.services.research import (
    InvalidStatusTransition,
    ResearchStatus,
    validate_transition,
)
from app.services.research_job import (
    ResearchNotFound,
    ResearchNotRunnable,
    run_research,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/researches", tags=["researches"])


def _handle_database_error(action: str) -> None:
    """Roll back the session and raise a generic 500 without leaking details."""
    logger.exception("Failed to %s research", action)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
    )


@router.post(
    "",
    response_model=ResearchResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_research(
    payload: ResearchCreate,
    db: Session = Depends(get_db),
) -> ResearchProject:
    """Create a new research project."""
    research = ResearchProject(**payload.model_dump())
    db.add(research)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        _handle_database_error("create")
    db.refresh(research)
    return research


@router.get("", response_model=ResearchListResponse)
def list_researches(
    db: Session = Depends(get_db),
) -> ResearchListResponse:
    """List research projects, newest first."""
    research_projects = db.scalars(
        select(ResearchProject).order_by(ResearchProject.created_at.desc())
    ).all()
    return ResearchListResponse(items=list(research_projects))


@router.get("/{research_id}", response_model=ResearchResponse)
def get_research(
    research_id: UUID,
    db: Session = Depends(get_db),
) -> ResearchProject:
    """Get a single research project by id."""
    research = db.get(ResearchProject, research_id)
    if research is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research not found",
        )
    return research


@router.patch("/{research_id}", response_model=ResearchResponse)
def update_research(
    research_id: UUID,
    payload: ResearchUpdate,
    db: Session = Depends(get_db),
) -> ResearchProject:
    """Update the editable fields of a research project.

    Status changes go through the research state machine; illegal transitions
    return 409 Conflict and leave the stored status untouched.
    """
    research = db.get(ResearchProject, research_id)
    if research is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research not found",
        )

    data = payload.model_dump(exclude_unset=True)
    new_status = data.pop("status", None)
    if new_status is not None:
        try:
            current_status = ResearchStatus(research.status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Current research status is invalid",
            ) from None
        if new_status != current_status:
            try:
                validate_transition(current_status, new_status)
            except InvalidStatusTransition:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Cannot transition research status from "
                        f"{current_status.value} to {new_status.value}"
                    ),
                ) from None
            research.status = new_status.value

    for field, value in data.items():
        setattr(research, field, value)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        _handle_database_error("update")
    db.refresh(research)
    return research


@router.delete("/{research_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_research(
    research_id: UUID,
    db: Session = Depends(get_db),
) -> Response:
    """Delete a research project."""
    research = db.get(ResearchProject, research_id)
    if research is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research not found",
        )
    db.delete(research)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        _handle_database_error("delete")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{research_id}/run", response_model=ResearchJobResponse)
def run_research_endpoint(
    research_id: UUID,
    db: Session = Depends(get_db),
) -> ResearchJob:
    """Start a research synchronously and return its finished job."""
    try:
        return run_research(db, research_id)
    except ResearchNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research not found",
        ) from None
    except ResearchNotRunnable as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from None
    except Exception:
        logger.exception("Failed to run research %s", research_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run research",
        ) from None


@router.get("/{research_id}/jobs", response_model=ResearchJobListResponse)
def list_research_jobs(
    research_id: UUID,
    db: Session = Depends(get_db),
) -> ResearchJobListResponse:
    """List the jobs of a research, newest first."""
    research = db.get(ResearchProject, research_id)
    if research is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research not found",
        )
    jobs = db.scalars(
        select(ResearchJob)
        .where(ResearchJob.research_id == research_id)
        .order_by(ResearchJob.created_at.desc())
    ).all()
    return ResearchJobListResponse(items=list(jobs))
