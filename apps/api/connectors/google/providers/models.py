"""Provider input/output contract models.

These models define the provider layer contract only. They deliberately do
not depend on FastAPI, SQLAlchemy, or the Research API schemas so that real
providers can be added later without touching the rest of the application.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class KeywordProviderRequest(BaseModel):
    """Normalized request for keyword discovery or metrics.

    ``seed_keyword`` must be non-empty. ``country_code`` and ``language_code``
    follow the project convention (e.g. US / en) and default to the same
    values used by the Research API.
    """

    seed_keyword: str = Field(min_length=1)
    country_code: str = "US"
    language_code: str = "en"


class KeywordCandidate(BaseModel):
    """A keyword candidate returned by a provider.

    ``source_type`` follows the project convention used by
    ``research_keyword.source_type`` (seed / ai_generated / provider /
    imported / manual). ``provider`` identifies which provider produced the
    candidate.
    """

    keyword_text: str
    normalized_keyword: str
    source_type: str
    provider: str
    raw_payload: dict[str, object] | list[object] | None = None


class KeywordMetric(BaseModel):
    """Point-in-time keyword demand metrics from a single provider.

    All external metric fields default to ``None`` because missing data must
    never be represented with fabricated values such as ``0``. A provider
    only fills in the fields it actually observed from the data source.
    """

    keyword_text: str
    estimated_monthly_searches: int | None = None
    cpc: float | None = None
    currency: str | None = None
    competition: float | None = None
    competition_level: str | None = None
    source: str | None = None
    retrieved_at: datetime | None = None
    provider_version: str | None = None
    raw_payload: dict[str, object] | None = None


class KeywordTrend(BaseModel):
    """A single relative-interest data point from a trend provider.

    ``value`` is the relative interest index (0-100) for ``keyword`` at
    ``time`` in ``country_code``. It is never an absolute search volume,
    CPC, or competition value. ``language_code`` is included when the data
    source can provide it (e.g. the Google Trends ``hl`` parameter).
    """

    keyword: str
    time: datetime
    value: float
    country_code: str
    language_code: str | None = None
    provider: str


class KeywordTrendResult(BaseModel):
    """Structured trend output for one keyword from a single provider.

    Mirrors the Trend data-source contract in docs/DATA_SOURCES.md: a
    relative-interest series, a coarse trend direction, related and rising
    queries, the requested period, and retrieval metadata.
    ``trend_series`` keeps the data source's original chronological order
    and contains no duplicate time points.
    """

    keyword: str
    country_code: str
    language_code: str | None = None
    timeframe: str
    trend_series: list[KeywordTrend]
    trend_direction: str | None = None
    related_queries: list[str] = []
    rising_queries: list[str] = []
    retrieved_at: datetime
    source: str | None = None
    provider_version: str | None = None
    raw_payload: dict[str, object] | None = None
