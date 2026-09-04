"""Google connector.

The connector owns Google-specific collection while exposing only the
source-agnostic :class:`CollectionResult` contract to the Demand Engine. It
delegates HTTP/parsing to the ported Google Suggest and Google Trends
providers and normalizes provider output through the Google mapper.
"""

import logging
from datetime import datetime, timezone

from connectors.base import (
    CollectionResult,
    CollectionStats,
    SourceRunResult,
    SourceRunStatus,
)
from connectors.google.mapper import (
    map_suggest_candidates,
    map_trend_candidates,
)
from connectors.google.query import GoogleQuery
from connectors.google.providers import (
    GoogleSuggestProvider,
    GoogleTrendsProvider,
    KeywordProviderRequest,
    ProviderNotConfiguredError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderResponseError,
    ProviderTimeoutError,
)

logger = logging.getLogger(__name__)


def _error_code(exc: Exception) -> str:
    """Map a provider exception to a stable error code."""
    if isinstance(exc, ProviderRateLimitError):
        return "provider_rate_limited"
    if isinstance(exc, ProviderTimeoutError):
        return "provider_timeout"
    if isinstance(exc, ProviderRequestError):
        return "provider_request_error"
    if isinstance(exc, ProviderResponseError):
        return "provider_response_error"
    if isinstance(exc, ProviderNotConfiguredError):
        return "provider_not_configured"
    return "unexpected_error"


class GoogleConnector:
    """Collects Google Suggest and Google Trends evidence for a seed query."""

    name = "google"

    def __init__(
        self,
        suggest_provider: GoogleSuggestProvider | None = None,
        trends_provider: GoogleTrendsProvider | None = None,
    ) -> None:
        self._suggest = suggest_provider or GoogleSuggestProvider()
        self._trends = trends_provider or GoogleTrendsProvider()

    def collect(self, query: GoogleQuery) -> CollectionResult:
        """Run the requested Google capabilities and return candidates."""
        provider_request = KeywordProviderRequest(
            seed_keyword=query.seed_query,
            country_code=query.country,
            language_code=query.language,
        )
        candidates = []
        source_results: list[SourceRunResult] = []
        collected_at = datetime.now(timezone.utc)

        if query.include_suggest:
            candidates.extend(
                self._collect_suggest(
                    query, provider_request, collected_at, source_results
                )
            )
        if query.include_trends:
            candidates.extend(
                self._collect_trends(
                    query, provider_request, collected_at, source_results
                )
            )

        counts = {
            source.capability: source.candidate_count for source in source_results
        }
        return CollectionResult(
            candidates=candidates,
            stats=CollectionStats(
                total_count=len(candidates),
                by_capability=counts,
            ),
            sources=source_results,
        )

    def _collect_suggest(
        self,
        query: GoogleQuery,
        provider_request: KeywordProviderRequest,
        collected_at: datetime,
        source_results: list[SourceRunResult],
    ) -> list:
        try:
            suggestions = self._suggest.discover_keywords(provider_request)
            mapped = map_suggest_candidates(query, suggestions, collected_at)
        except Exception as exc:
            logger.warning("Google Suggest collection failed: %s", type(exc).__name__)
            source_results.append(self._failed_result("suggest", exc))
            return []
        source_results.append(
            SourceRunResult(
                capability="suggest",
                status=SourceRunStatus.SUCCESS,
                candidate_count=len(mapped),
            )
        )
        return mapped

    def _collect_trends(
        self,
        query: GoogleQuery,
        provider_request: KeywordProviderRequest,
        collected_at: datetime,
        source_results: list[SourceRunResult],
    ) -> list:
        try:
            trend_results = self._trends.get_keyword_trends(
                [query.seed_query], provider_request
            )
            mapped = map_trend_candidates(query, trend_results, collected_at)
        except Exception as exc:
            logger.warning("Google Trends collection failed: %s", type(exc).__name__)
            source_results.append(self._failed_result("trends", exc))
            return []
        source_results.append(
            SourceRunResult(
                capability="trends",
                status=SourceRunStatus.SUCCESS,
                candidate_count=len(mapped),
            )
        )
        return mapped

    @staticmethod
    def _failed_result(capability: str, exc: Exception) -> SourceRunResult:
        """Build a failed SourceRunResult without leaking stack traces."""
        return SourceRunResult(
            capability=capability,
            status=SourceRunStatus.FAILED,
            candidate_count=0,
            error_code=_error_code(exc),
            error_message=str(exc) or type(exc).__name__,
        )


__all__ = ["GoogleConnector", "GoogleQuery"]
