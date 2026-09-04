"""Research and research job data models.

Follows docs/DATABASE.md (research_project / research_job).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin, utcnow

if TYPE_CHECKING:
    from app.models.keywords import ResearchKeyword


class ResearchProject(Base, UUIDPrimaryKeyMixin):
    """A single keyword research task/project."""

    __tablename__ = "research_project"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    seed_keyword: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    country_code: Mapped[str] = mapped_column(
        String(10), nullable=False, default="US"
    )
    language_code: Mapped[str] = mapped_column(
        String(20), nullable=False, default="en"
    )
    # Allowed values: draft / running / completed / failed / cancelled
    # (formal state machine: app/services/research.py).
    # Python-side defaults keep the model and API schemas consistent.
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    research_keywords: Mapped[list["ResearchKeyword"]] = relationship(
        back_populates="research", cascade="all, delete-orphan"
    )
    research_jobs: Mapped[list["ResearchJob"]] = relationship(
        back_populates="research", cascade="all, delete-orphan"
    )


class ResearchJob(Base, UUIDPrimaryKeyMixin):
    """A single execution job for a research project."""

    __tablename__ = "research_job"

    research_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("research_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Allowed values: pending / running / completed / failed / cancelled
    # (formal state machine: app/services/research_job.py).
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    research: Mapped["ResearchProject"] = relationship(
        back_populates="research_jobs"
    )
