"""Request/response schemas for the Google collection API."""

from connectors.base import (
    CollectionStats,
    DemandSignalCandidate,
    SourceRunResult,
)
from pydantic import BaseModel, computed_field


class GoogleCollectStats(CollectionStats):
    """Google collection statistics with source-specific convenience counts."""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def suggest_count(self) -> int:
        return self.by_capability.get("suggest", 0)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def trend_count(self) -> int:
        return self.by_capability.get("trends", 0)


class GoogleCollectResponse(BaseModel):
    """Full result of a Google collection request."""

    items: list[DemandSignalCandidate]
    stats: GoogleCollectStats
    sources: list[SourceRunResult]


__all__ = ["GoogleCollectResponse", "GoogleCollectStats"]
