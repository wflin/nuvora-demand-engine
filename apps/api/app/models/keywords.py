"""Keyword, research-keyword association, and keyword metric snapshot models.

Follows docs/DATABASE.md (keyword / research_keyword / keyword_metric_snapshot).
Metrics are source-agnostic observations, never fabricated search volumes:
every nullable metric field defaults to NULL (unknown), not 0.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin, utcnow

if TYPE_CHECKING:
    from app.models.research import ResearchProject


def normalize_keyword(keyword: str) -> str:
    """Deterministic normalization for dedup/matching.

    Strategy: trim, lowercase, and collapse runs of whitespace to a single
    space. Intentionally simple; no NLP in this task.
    """
    return " ".join(keyword.strip().lower().split())


class Keyword(Base, UUIDPrimaryKeyMixin):
    """A globally shared keyword entity, independent of any single research."""

    __tablename__ = "keyword"
    __table_args__ = (
        UniqueConstraint(
            "normalized_keyword",
            "language_code",
            name="uq_keyword_normalized_keyword_language_code",
        ),
    )

    keyword_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_keyword: Mapped[str] = mapped_column(Text, nullable=False)
    language_code: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    research_keywords: Mapped[list["ResearchKeyword"]] = relationship(
        back_populates="keyword", cascade="all, delete-orphan"
    )
    metric_snapshots: Mapped[list["KeywordMetricSnapshot"]] = relationship(
        back_populates="keyword", cascade="all, delete-orphan"
    )


class ResearchKeyword(Base, UUIDPrimaryKeyMixin):
    """Association between a research project and a keyword."""

    __tablename__ = "research_keyword"
    __table_args__ = (
        UniqueConstraint(
            "research_id",
            "keyword_id",
            name="uq_research_keyword_research_id_keyword_id",
        ),
    )

    research_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    keyword_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("keyword.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Allowed values: seed / ai_generated / provider / imported / manual
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    intent: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    research: Mapped["ResearchProject"] = relationship(
        back_populates="research_keywords"
    )
    keyword: Mapped["Keyword"] = relationship(back_populates="research_keywords")


class KeywordMetricSnapshot(Base, UUIDPrimaryKeyMixin):
    """A point-in-time observation of keyword demand metrics from one source."""

    __tablename__ = "keyword_metric_snapshot"

    keyword_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("keyword.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    research_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    country_code: Mapped[str] = mapped_column(String(10), nullable=False)
    language_code: Mapped[str] = mapped_column(String(20), nullable=False)
    estimated_monthly_searches: Mapped[int | None] = mapped_column(BigInteger)
    cpc: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    currency: Mapped[str | None] = mapped_column(String(10))
    competition: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    competition_level: Mapped[str | None] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    provider_version: Mapped[str | None] = mapped_column(String(100))
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)

    keyword: Mapped["Keyword"] = relationship(back_populates="metric_snapshots")
    research: Mapped["ResearchProject"] = relationship()