"""Source-agnostic connector contracts.

The Demand Engine (API, services, domain) depends only on the types defined
here. Connectors translate their source-specific results into
:class:`DemandSignalCandidate` records and report per-source run status so
partial failures are never hidden.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SourceRunStatus(StrEnum):
    """Outcome of one source capability within a collection run."""

    SUCCESS = "success"
    FAILED = "failed"


class DemandSignalCandidate(BaseModel):
    """A normalized evidence candidate produced by a connector.

    Field layout stays compatible with the ``DemandSignal`` entity in
    docs/03-DATA-MODEL.md. This is the connector output contract only;
    persistence is introduced in a later phase.
    """

    source: str
    source_type: str
    external_id: str | None = None
    keyword: str | None = None
    normalized_keyword: str | None = None
    title: str | None = None
    content: str | None = None
    url: str | None = None
    language: str | None = None
    country: str | None = None
    occurred_at: datetime | None = None
    collected_at: datetime = Field(default_factory=_utcnow)
    metrics: dict[str, Any] = Field(default_factory=dict)
    raw_data: dict[str, Any] = Field(default_factory=dict)
    normalized_text: str | None = None
    fingerprint: str
    confidence: float | None = None


class SourceRunResult(BaseModel):
    """Observable status of one source capability in a collection run."""

    capability: str
    status: SourceRunStatus
    candidate_count: int = 0
    error_code: str | None = None
    error_message: str | None = None


class CollectionStats(BaseModel):
    """Aggregated counts for a collection run."""

    total_count: int = 0
    by_capability: dict[str, int] = Field(default_factory=dict)


class CollectionResult(BaseModel):
    """Normalized output of a connector ``collect`` invocation."""

    candidates: list[DemandSignalCandidate] = Field(default_factory=list)
    stats: CollectionStats = Field(default_factory=CollectionStats)
    sources: list[SourceRunResult] = Field(default_factory=list)

    @property
    def executed_capabilities(self) -> list[str]:
        """Return the source capabilities that were attempted."""
        return [source.capability for source in self.sources]

    @property
    def all_requested_sources_failed(self) -> bool:
        """True when at least one source ran and every run failed."""
        return bool(self.sources) and all(
            source.status == SourceRunStatus.FAILED for source in self.sources
        )


class SourceQuery(BaseModel):
    """Base query contract shared by all source connectors."""

    seed_query: str
    country: str = "US"
    language: str = "en"


class Connector(ABC):
    """Abstract connector contract: ``collect(query) -> CollectionResult``."""

    name: str

    @abstractmethod
    def collect(self, query: SourceQuery) -> CollectionResult:
        """Collect and normalize evidence for ``query``."""


__all__ = [
    "CollectionResult",
    "CollectionStats",
    "Connector",
    "DemandSignalCandidate",
    "SourceQuery",
    "SourceRunResult",
    "SourceRunStatus",
]
