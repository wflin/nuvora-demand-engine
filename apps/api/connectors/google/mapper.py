"""Google result -> DemandSignalCandidate mapping.

The mapper is pure logic with no network access: it converts provider output
into the unified candidate contract while preserving raw payloads and stable
fingerprints.
"""

from datetime import datetime, timezone

from app.core.fingerprint import signal_fingerprint
from app.core.text import normalize_keyword, normalize_text
from connectors.base import DemandSignalCandidate
from connectors.google.query import GoogleQuery
from connectors.google.providers.models import (
    KeywordCandidate,
    KeywordTrend,
    KeywordTrendResult,
)

SOURCE_NAME = "google"
SUGGEST_SOURCE_TYPE = "search_suggestion"
TREND_SOURCE_TYPE = "search_trend"


def _fingerprint(
    *,
    source_type: str,
    country: str,
    language: str,
    normalized_keyword: str,
    timeframe: str | None = None,
    time_bucket: str | None = None,
) -> str:
    return signal_fingerprint(
        source=SOURCE_NAME,
        source_type=source_type,
        country=country,
        language=language,
        normalized_keyword=normalized_keyword,
        timeframe=timeframe,
        time_bucket=time_bucket,
    )


def _trend_time_bucket(series: list[KeywordTrend]) -> str | None:
    """Return the canonical Google Trends time bucket for ``series``.

    Prefers the last valid time point Google Trends returned as the current
    candidate's external time bucket. Returns ``None`` when the series is
    empty or has no usable point; a time value is never fabricated here.
    """

    if not series:
        return None
    point_time = series[-1].time
    if point_time.tzinfo is None:
        point_time = point_time.replace(tzinfo=timezone.utc)
    else:
        point_time = point_time.astimezone(timezone.utc)
    return point_time.isoformat()


def map_suggest_candidates(
    query: GoogleQuery,
    suggestions: list[KeywordCandidate],
    collected_at: datetime,
) -> list[DemandSignalCandidate]:
    """Map Google Suggest suggestions into demand signal candidates."""
    mapped: list[DemandSignalCandidate] = []
    for suggestion in suggestions:
        normalized_keyword_value = normalize_keyword(suggestion.keyword_text)
        mapped.append(
            DemandSignalCandidate(
                source=SOURCE_NAME,
                source_type=SUGGEST_SOURCE_TYPE,
                keyword=suggestion.keyword_text,
                normalized_keyword=normalized_keyword_value,
                language=query.language,
                country=query.country,
                collected_at=collected_at,
                metrics={},
                raw_data={
                    "provider": suggestion.provider,
                    "raw_payload": suggestion.raw_payload,
                },
                normalized_text=normalize_text(suggestion.keyword_text),
                fingerprint=_fingerprint(
                    source_type=SUGGEST_SOURCE_TYPE,
                    country=query.country,
                    language=query.language,
                    normalized_keyword=normalized_keyword_value,
                ),
            )
        )
    return mapped


def _series_to_json(points: list) -> list[dict]:
    return [
        {"time": point.time.isoformat(), "value": point.value} for point in points
    ]


def map_trend_candidates(
    query: GoogleQuery,
    results: list[KeywordTrendResult],
    collected_at: datetime,
) -> list[DemandSignalCandidate]:
    """Map Google Trends summaries into demand signal candidates."""
    mapped: list[DemandSignalCandidate] = []
    for result in results:
        normalized_keyword_value = normalize_keyword(result.keyword)
        time_bucket = _trend_time_bucket(result.trend_series)
        mapped.append(
            DemandSignalCandidate(
                source=SOURCE_NAME,
                source_type=TREND_SOURCE_TYPE,
                keyword=result.keyword,
                normalized_keyword=normalized_keyword_value,
                language=query.language,
                country=query.country,
                collected_at=collected_at,
                metrics={
                    "interest_over_time": _series_to_json(result.trend_series),
                    "trend_direction": result.trend_direction,
                    "related_queries": result.related_queries,
                    "rising_queries": result.rising_queries,
                    "timeframe": result.timeframe,
                    "time_bucket": time_bucket,
                    "provider_version": result.provider_version,
                },
                raw_data={
                    "provider": result.source,
                    "raw_payload": result.raw_payload,
                },
                normalized_text=normalize_text(result.keyword),
                fingerprint=_fingerprint(
                    source_type=TREND_SOURCE_TYPE,
                    country=query.country,
                    language=query.language,
                    normalized_keyword=normalized_keyword_value,
                    timeframe=result.timeframe,
                    time_bucket=time_bucket,
                ),
            )
        )
    return mapped


__all__ = ["map_suggest_candidates", "map_trend_candidates"]
