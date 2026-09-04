"""Research job detail API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models import ResearchJob
from app.schemas.research_job import ResearchJobResponse

router = APIRouter(prefix="/research-jobs", tags=["research-jobs"])


@router.get("/{job_id}", response_model=ResearchJobResponse)
def get_research_job(
    job_id: UUID,
    db: Session = Depends(get_db),
) -> ResearchJob:
    """Get a single research job by id."""
    job = db.get(ResearchJob, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research job not found",
        )
    return job
