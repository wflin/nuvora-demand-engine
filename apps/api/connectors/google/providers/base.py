"""Keyword provider abstraction.

A provider is: ``input -> external data source -> normalized output``.
This layer has no knowledge of FastAPI, SQLAlchemy, HTTP routing, or the
database. Research services are responsible for persisting provider output.
"""

from abc import ABC, abstractmethod

from .models import (
    KeywordCandidate,
    KeywordMetric,
    KeywordProviderRequest,
    KeywordTrendResult,
)
from .exceptions import ProviderNotConfiguredError


class KeywordProvider(ABC):
    """Abstract interface for keyword data providers.

    Subclasses must set the ``name`` and ``version`` class attributes and
    implement both abstract methods. Adding a real provider (for example a
    Google Keyword Planner or third-party provider) later only requires a new
    ``KeywordProvider`` implementation; ResearchJob business logic stays
    unchanged.
    """

    name: str
    version: str

    @abstractmethod
    def discover_keywords(
        self,
        request: KeywordProviderRequest,
    ) -> list[KeywordCandidate]:
        """Discover keyword candidates related to the request's seed keyword."""

    @abstractmethod
    def get_keyword_metrics(
        self,
        keywords: list[str],
        request: KeywordProviderRequest,
    ) -> list[KeywordMetric]:
        """Return demand metrics for the given keywords and request context."""

    def get_keyword_trends(
        self,
        keywords: list[str],
        request: KeywordProviderRequest,
        timeframe: str = "today 12-m",
    ) -> list[KeywordTrendResult]:
        """Return trend data for the given keywords and request context.

        Trend capability is optional for a provider. The default
        implementation raises :class:`ProviderNotConfiguredError` so
        existing providers that do not support trends keep working
        unchanged; a real trend provider overrides this method.
        """
        raise ProviderNotConfiguredError(
            f"Provider {self.name!r} does not provide keyword trends"
        )


class StubKeywordProvider(KeywordProvider):
    """Placeholder provider that intentionally produces no data.

    Both methods return empty lists. The stub never fabricates keywords,
    search volumes, CPC, or competition values; it exists only until real
    providers are implemented in later tasks.
    """

    name = "stub"
    version = "0.0.0"

    def discover_keywords(
        self,
        request: KeywordProviderRequest,
    ) -> list[KeywordCandidate]:
        """Return no candidates (empty list)."""
        return []

    def get_keyword_metrics(
        self,
        keywords: list[str],
        request: KeywordProviderRequest,
    ) -> list[KeywordMetric]:
        """Return no metrics (empty list)."""
        return []


class ProviderRegistry:
    """Lightweight registry mapping provider names to provider instances.

    This is intentionally a plain registry, not a dependency-injection
    container. It lets the application look up a provider by name (for
    example ``google_keyword_planner`` in the future) without coupling the
    caller to a concrete implementation.
    """

    def __init__(self) -> None:
        self._providers: dict[str, KeywordProvider] = {}

    def register(self, name: str, provider: KeywordProvider) -> None:
        """Register ``provider`` under ``name``; reject duplicates."""
        if not isinstance(provider, KeywordProvider):
            raise TypeError(f"{name!r} must be a KeywordProvider instance")
        if name in self._providers:
            raise ValueError(f"Provider {name!r} is already registered")
        self._providers[name] = provider

    def get(self, name: str) -> KeywordProvider:
        """Return the registered provider for ``name``."""
        try:
            return self._providers[name]
        except KeyError:
            raise KeyError(f"Provider {name!r} is not registered") from None
