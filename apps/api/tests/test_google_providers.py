"""Tests for the provider abstraction layer.

Pure unit tests: no network, no Google API, no API key, no PostgreSQL.
"""

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from connectors.google.providers import (
    KeywordCandidate,
    KeywordMetric,
    KeywordProvider,
    KeywordProviderRequest,
    ProviderAuthenticationError,
    ProviderError,
    ProviderNotConfiguredError,
    ProviderRateLimitError,
    ProviderRegistry,
    ProviderRequestError,
    ProviderResponseError,
    StubKeywordProvider,
)

PROVIDER_DIR = (
    Path(__file__).resolve().parents[1] / "connectors" / "google" / "providers"
)


def test_keyword_provider_abstract_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        KeywordProvider()  # type: ignore[abstract]


def test_stub_keyword_provider_can_be_instantiated() -> None:
    provider = StubKeywordProvider()
    assert provider.name == "stub"
    assert provider.version == "0.0.0"


def test_provider_request_created_with_defaults() -> None:
    request = KeywordProviderRequest(seed_keyword="coffee")
    assert request.seed_keyword == "coffee"
    assert request.country_code == "US"
    assert request.language_code == "en"


def test_provider_request_created_with_explicit_context() -> None:
    request = KeywordProviderRequest(
        seed_keyword="coffee",
        country_code="GB",
        language_code="en",
    )
    assert request.seed_keyword == "coffee"
    assert request.country_code == "GB"
    assert request.language_code == "en"


def test_provider_request_rejects_empty_seed_keyword() -> None:
    with pytest.raises(ValidationError):
        KeywordProviderRequest(seed_keyword="")


def test_keyword_candidate_created() -> None:
    candidate = KeywordCandidate(
        keyword_text="coffee brewing",
        normalized_keyword="coffee brewing",
        source_type="provider",
        provider="stub",
    )
    assert candidate.keyword_text == "coffee brewing"
    assert candidate.normalized_keyword == "coffee brewing"
    assert candidate.source_type == "provider"
    assert candidate.provider == "stub"


def test_keyword_metric_allows_all_metrics_none() -> None:
    metric = KeywordMetric(keyword_text="coffee")
    assert metric.keyword_text == "coffee"
    assert metric.estimated_monthly_searches is None
    assert metric.cpc is None
    assert metric.currency is None
    assert metric.competition is None
    assert metric.competition_level is None
    assert metric.source is None
    assert metric.retrieved_at is None
    assert metric.provider_version is None
    assert metric.raw_payload is None


def test_keyword_metric_with_explicit_values() -> None:
    metric = KeywordMetric(
        keyword_text="coffee",
        source="test",
        provider_version="0.0.0",
        raw_payload={"note": "no fabricated metrics"},
    )
    assert metric.source == "test"
    assert metric.provider_version == "0.0.0"
    assert metric.raw_payload == {"note": "no fabricated metrics"}


def test_stub_provider_returns_empty_results_with_correct_structure() -> None:
    provider = StubKeywordProvider()
    request = KeywordProviderRequest(seed_keyword="coffee")
    candidates = provider.discover_keywords(request)
    metrics = provider.get_keyword_metrics(["coffee"], request)
    assert isinstance(candidates, list)
    assert candidates == []
    assert isinstance(metrics, list)
    assert metrics == []


def test_provider_error_hierarchy() -> None:
    assert issubclass(ProviderNotConfiguredError, ProviderError)
    assert issubclass(ProviderAuthenticationError, ProviderError)
    assert issubclass(ProviderRateLimitError, ProviderError)
    assert issubclass(ProviderRequestError, ProviderError)
    assert issubclass(ProviderResponseError, ProviderError)
    for error in (
        ProviderNotConfiguredError("a"),
        ProviderAuthenticationError("b"),
        ProviderRateLimitError("c"),
        ProviderRequestError("d"),
        ProviderResponseError("e"),
    ):
        assert isinstance(error, ProviderError)


def test_provider_error_message_preserved_without_secrets() -> None:
    message = "Provider is not configured"
    error = ProviderNotConfiguredError(message)
    assert str(error) == message
    lowered = str(error).lower()
    assert "api_key" not in lowered
    assert "password" not in lowered
    assert "authorization" not in lowered
    assert "database_url" not in lowered


def test_provider_registry_register_and_get() -> None:
    registry = ProviderRegistry()
    provider = StubKeywordProvider()
    registry.register("stub", provider)
    assert registry.get("stub") is provider


def test_provider_registry_unknown_name_raises_key_error() -> None:
    registry = ProviderRegistry()
    with pytest.raises(KeyError):
        registry.get("missing")


def test_provider_registry_rejects_duplicate_name() -> None:
    registry = ProviderRegistry()
    registry.register("stub", StubKeywordProvider())
    with pytest.raises(ValueError):
        registry.register("stub", StubKeywordProvider())


def test_provider_registry_rejects_non_provider() -> None:
    registry = ProviderRegistry()
    with pytest.raises(TypeError):
        registry.register("not_a_provider", object())  # type: ignore[arg-type]


def imported_module_names(source: str) -> set[str]:
    """Return the top-level module names imported by ``source``."""
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def test_provider_layer_does_not_import_fastapi_or_sqlalchemy() -> None:
    sources = [
        PROVIDER_DIR / "__init__.py",
        PROVIDER_DIR / "base.py",
        PROVIDER_DIR / "models.py",
        PROVIDER_DIR / "exceptions.py",
        PROVIDER_DIR / "google_suggest.py",
        PROVIDER_DIR / "google_trends.py",
    ]
    for source in sources:
        imports = imported_module_names(source.read_text(encoding="utf-8"))
        assert "fastapi" not in imports
        assert "sqlalchemy" not in imports
