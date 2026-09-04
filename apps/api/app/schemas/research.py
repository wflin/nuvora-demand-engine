"""Pydantic schemas for the ResearchProject API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.services.research import ResearchStatus


class ResearchCreate(BaseModel):
    """Payload for creating a research project.

    Defaults mirror the ResearchProject model defaults so omitted values
    behave consistently.
    """

    name: str = Field(min_length=1, max_length=200)
    seed_keyword: str = Field(min_length=1)
    description: str | None = None
    country_code: str = "US"
    language_code: str = "en"
    status: ResearchStatus = ResearchStatus.DRAFT


class ResearchUpdate(BaseModel):
    """Payload for updating a research project; only sent fields are applied."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    seed_keyword: str | None = Field(default=None, min_length=1)
    description: str | None = None
    country_code: str | None = None
    language_code: str | None = None
    status: ResearchStatus | None = None


class ResearchResponse(BaseModel):
    """Research project as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    seed_keyword: str
    description: str | None
    country_code: str
    language_code: str
    status: str
    created_at: datetime
    updated_at: datetime


class ResearchListResponse(BaseModel):
    """List of research projects, newest first."""

    items: list[ResearchResponse]
