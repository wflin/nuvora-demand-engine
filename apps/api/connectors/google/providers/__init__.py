"""Keyword provider abstraction layer for the Google connector.

Providers convert external keyword data sources into normalized output. This
layer stays independent of FastAPI, SQLAlchemy and the database.
"""

from .base import KeywordProvider, ProviderRegistry, StubKeywordProvider
from .google_suggest import GoogleSuggestProvider
from .google_trends import GoogleTrendsProvider
from .exceptions import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderNotConfiguredError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from .models import (
    KeywordCandidate,
    KeywordMetric,
    KeywordProviderRequest,
    KeywordTrend,
    KeywordTrendResult,
)

__all__ = [
    "GoogleSuggestProvider",
    "GoogleTrendsProvider",
    "KeywordCandidate",
    "KeywordMetric",
    "KeywordProvider",
    "KeywordProviderRequest",
    "KeywordTrend",
    "KeywordTrendResult",
    "ProviderAuthenticationError",
    "ProviderError",
    "ProviderNotConfiguredError",
    "ProviderRateLimitError",
    "ProviderRegistry",
    "ProviderRequestError",
    "ProviderResponseError",
    "ProviderTimeoutError",
    "StubKeywordProvider",
]
