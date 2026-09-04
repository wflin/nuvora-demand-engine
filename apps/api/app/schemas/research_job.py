"""Pydantic schemas for the ResearchJob API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.services.research_job import ResearchJobStatus


class ResearchJobResponse(BaseModel):
    """Research job as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    research_id: UUID
    status: ResearchJobStatus
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class ResearchJobListResponse(BaseModel):
    """List of research jobs for a research, newest first."""

    items: list[ResearchJobResponse]
