"""Offline tests for the Google connector, mapper and collection API.

These tests never contact the real Google network. Google-shaped fixture
responses (the same shapes used by the provider tests) are fed through the
real providers, and fake providers are injected into GoogleConnector or the
API dependency only to exercise orchestration, partial-failure and error
behavior.
"""

import json
import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.sources_google import get_google_connector
from app.core.fingerprint import signal_fingerprint
from app.core.text import normalize_keyword
from app.main import app
from connectors.base import SourceRunStatus
from connectors.google import mapper as google_mapper
from connectors.google.google_connector import GoogleConnector
from connectors.google.providers import (
    GoogleSuggestProvider,
    GoogleTrendsProvider,
    KeywordCandidate,
    KeywordProviderRequest,
    KeywordTrend,
    KeywordTrendResult,
    ProviderNotConfiguredError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from connectors.google.query import GoogleQuery

COLLECT_URL = "/api/v1/sources/google/collect"
HEX64 = re.compile(r"[0-9a-f]{64}")


def make_query(
    seed_query: str = "coffee",
    country: str = "US",
    language: str = "en",
) -> GoogleQuery:
    """Build the connector query used across these tests."""
    return GoogleQuery(
        seed_query=seed_query,
        country=country,
        language=language,
    )


def make_suggestion(keyword_text: str) -> KeywordCandidate:
    """Build a suggestion in the real GoogleSuggestProvider output shape."""
    return KeywordCandidate(
        keyword_text=keyword_text,
        normalized_keyword=normalize_keyword(keyword_text),
        source_type="provider",
        provider="google_suggest",
        raw_payload={"suggestion": keyword_text},
    )


def make_trend_result(
    keyword: str = "coffee",
    values: tuple[float, ...] = (50.0, 60.0, 80.0),
    timeframe: str = "today 12-m",
) -> KeywordTrendResult:
    """Build a trend result in the real GoogleTrendsProvider output shape."""
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    series = [
        KeywordTrend(
            keyword=keyword,
            time=start + timedelta(days=7 * index),
            value=value,
            country_code="US",
            language_code="en",
            provider="google_trends",
        )
        for index, value in enumerate(values)
    ]
    return KeywordTrendResult(
        keyword=keyword,
        country_code="US",
        language_code="en",
        timeframe=timeframe,
        trend_series=series,
        trend_direction="rising",
        related_queries=["coffee beans", "cold brew"],
        rising_queries=["espresso machine"],
        retrieved_at=start,
        source="google_trends",
        provider_version="1",
        raw_payload={"interest_over_time": "fixture"},
    )


def expected_fingerprint(
    source_type: str,
    keyword: str,
    *,
    country: str = "US",
    language: str = "en",
) -> str:
    """Compute the documented SHA-256 fingerprint for a candidate."""
    return signal_fingerprint(
        source="google",
        source_type=source_type,
        country=country,
        language=language,
        normalized_keyword=normalize_keyword(keyword),
    )


def expected_trend_fingerprint(
    keyword: str,
    *,
    timeframe: str,
    time_bucket: str | None,
    country: str = "US",
    language: str = "en",
) -> str:
    """Compute the documented SHA-256 fingerprint for a trend candidate."""
    return signal_fingerprint(
        source="google",
        source_type="search_trend",
        country=country,
        language=language,
        normalized_keyword=normalize_keyword(keyword),
        timeframe=timeframe,
        time_bucket=time_bucket,
    )


class FakeSuggestProvider:
    """Injectable suggest provider that returns scripted output/errors."""

    def __init__(
        self,
        candidates: list[KeywordCandidate] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.candidates = list(candidates or [])
        self.error = error

    def discover_keywords(
        self,
        request: KeywordProviderRequest,
    ) -> list[KeywordCandidate]:
        if self.error is not None:
            raise self.error
        return self.candidates


class FakeTrendsProvider:
    """Injectable trends provider that returns scripted output/errors."""

    def __init__(
        self,
        results: list[KeywordTrendResult] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.results = list(results or [])
        self.error = error

    def get_keyword_trends(
        self,
        keywords: list[str],
        request: KeywordProviderRequest,
        timeframe: str = "today 12-m",
    ) -> list[KeywordTrendResult]:
        if self.error is not None:
            raise self.error
        return self.results


class SuggestStubRequester:
    """Deterministic suggest transport mirroring the provider tests."""

    def __init__(
        self,
        body: bytes,
        content_type: str | None = None,
        status: int = 200,
    ) -> None:
        self.body = body
        self.content_type = content_type
        self.status = status

    def get(
        self,
        url: str,
        headers: dict[str, str],
        timeout: float,
    ) -> tuple[int, bytes, str | None]:
        return self.status, self.body, self.content_type


XSSI = b")]}'\n"
COOKIE_HEADERS = {
    "set-cookie": (
        "NID=511=abc123; Expires=Wed, 01 Jan 2027 00:00:00 GMT; "
        "Path=/; Domain=.google.com; HttpOnly"
    )
}


def _xssi(payload: object) -> bytes:
    return XSSI + json.dumps(payload).encode("utf-8")


def _explore_response() -> bytes:
    widgets = [
        {
            "id": "TIMESERIES",
            "request": {"comparisonItem": [], "resolution": "WEEK"},
            "token": "ts-token",
        },
        {
            "id": "RELATED_QUERIES",
            "request": {"comparisonItem": [], "metric": ["TOP", "RISING"]},
            "token": "rq-token",
        },
    ]
    return _xssi({"widgets": widgets})


def _timeline_response(*values: int) -> bytes:
    timeline = [
        {
            "time": str(1700000000 + index * 604800),
            "formattedTime": f"week-{index}",
            "value": [value],
        }
        for index, value in enumerate(values)
    ]
    return _xssi({"default": {"timelineData": timeline}})


def _related_response(top: list[str], rising: list[str]) -> bytes:
    ranked = [
        {
            "rankedKeyword": [
                {"query": query, "value": index} for index, query in enumerate(top)
            ]
        },
        {"rankedKeyword": [{"query": query, "value": "+900%"} for query in rising]},
    ]
    return _xssi({"default": {"rankedList": ranked}})


class TrendsStubRequester:
    """Deterministic trends transport mirroring the provider tests."""

    def __init__(
        self,
        responses: list[tuple[int, bytes, str | None, dict[str, str]]],
    ) -> None:
        self.responses = list(responses)

    def _next(
        self,
        url: str,
        headers: dict[str, str],
        timeout: float,
    ) -> tuple[int, bytes, str | None, dict[str, str]]:
        return self.responses.pop(0)

    def get(
        self,
        url: str,
        headers: dict[str, str],
        timeout: float,
    ) -> tuple[int, bytes, str | None, dict[str, str]]:
        return self._next(url, headers, timeout)

    def post(
        self,
        url: str,
        headers: dict[str, str],
        timeout: float,
    ) -> tuple[int, bytes, str | None, dict[str, str]]:
        return self._next(url, headers, timeout)


# Mapper -----------------------------------------------------------------


def test_suggest_mapping_produces_candidate_contract() -> None:
    query = make_query()
    collected_at = datetime(2026, 9, 4, tzinfo=timezone.utc)
    suggestions = [make_suggestion("Coffee Maker"), make_suggestion("coffee grinder")]

    mapped = google_mapper.map_suggest_candidates(query, suggestions, collected_at)

    assert len(mapped) == 2
    first = mapped[0]
    assert first.source == "google"
    assert first.source_type == "search_suggestion"
    assert first.keyword == "Coffee Maker"
    assert first.normalized_keyword == "coffee maker"
    assert first.normalized_text == "coffee maker"
    assert first.language == "en"
    assert first.country == "US"
    assert first.collected_at == collected_at
    assert first.metrics == {}
    assert first.raw_data == {
        "provider": "google_suggest",
        "raw_payload": {"suggestion": "Coffee Maker"},
    }
    assert first.external_id is None
    assert first.url is None
    assert first.confidence is None
    assert HEX64.fullmatch(first.fingerprint)
    assert first.fingerprint == expected_fingerprint(
        "search_suggestion", "Coffee Maker"
    )


def test_suggest_mapping_preserves_chinese_keyword() -> None:
    query = make_query(seed_query="上海 股票", country="CN", language="zh-CN")
    collected_at = datetime(2026, 9, 4, tzinfo=timezone.utc)

    mapped = google_mapper.map_suggest_candidates(
        query, [make_suggestion("上海 股票")], collected_at
    )

    assert mapped[0].keyword == "上海 股票"
    assert mapped[0].normalized_keyword == "上海 股票"
    assert mapped[0].language == "zh-CN"
    assert mapped[0].country == "CN"


def test_suggest_fingerprint_is_stable_and_context_sensitive() -> None:
    suggestion = make_suggestion("coffee maker")
    query_us = make_query()
    query_gb = make_query(country="GB")
    first_collected = datetime(2026, 1, 1, tzinfo=timezone.utc)
    later_collected = datetime(2026, 9, 4, tzinfo=timezone.utc)

    same_time = google_mapper.map_suggest_candidates(
        query_us, [suggestion], first_collected
    )
    later = google_mapper.map_suggest_candidates(
        query_us, [suggestion], later_collected
    )
    other_country = google_mapper.map_suggest_candidates(
        query_gb, [suggestion], first_collected
    )

    assert same_time[0].fingerprint == later[0].fingerprint
    assert same_time[0].fingerprint != other_country[0].fingerprint
    assert other_country[0].fingerprint == expected_fingerprint(
        "search_suggestion", "coffee maker", country="GB"
    )


def test_trend_mapping_produces_candidate_contract() -> None:
    query = make_query()
    collected_at = datetime(2026, 9, 4, tzinfo=timezone.utc)
    result = make_trend_result(values=(10.0, 30.0, 90.0))

    mapped = google_mapper.map_trend_candidates(query, [result], collected_at)

    assert len(mapped) == 1
    first = mapped[0]
    assert first.source == "google"
    assert first.source_type == "search_trend"
    assert first.keyword == "coffee"
    assert first.normalized_keyword == "coffee"
    assert first.normalized_text == "coffee"
    assert first.country == "US"
    assert first.language == "en"
    assert first.collected_at == collected_at

    metrics = first.metrics
    series = metrics["interest_over_time"]
    assert [point["value"] for point in series] == [10.0, 30.0, 90.0]
    for point in series:
        datetime.fromisoformat(point["time"])
    assert metrics["trend_direction"] == "rising"
    assert metrics["related_queries"] == ["coffee beans", "cold brew"]
    assert metrics["rising_queries"] == ["espresso machine"]
    assert metrics["timeframe"] == "today 12-m"
    assert metrics["time_bucket"] == "2026-01-15T00:00:00+00:00"
    assert metrics["provider_version"] == "1"

    assert first.raw_data == {
        "provider": "google_trends",
        "raw_payload": {"interest_over_time": "fixture"},
    }
    assert HEX64.fullmatch(first.fingerprint)
    assert first.fingerprint == expected_trend_fingerprint(
        "coffee",
        timeframe="today 12-m",
        time_bucket="2026-01-15T00:00:00+00:00",
    )


def test_trend_fingerprint_stable_for_same_time_bucket() -> None:
    query = make_query()
    collected_at = datetime(2026, 9, 4, tzinfo=timezone.utc)
    first = google_mapper.map_trend_candidates(
        query,
        [make_trend_result(values=(50.0, 60.0, 80.0))],
        collected_at,
    )[0]
    second = google_mapper.map_trend_candidates(
        query,
        [make_trend_result(values=(10.0, 20.0, 30.0))],
        collected_at,
    )[0]

    assert first.metrics["time_bucket"] == "2026-01-15T00:00:00+00:00"
    assert second.metrics["time_bucket"] == first.metrics["time_bucket"]
    assert first.metrics["timeframe"] == second.metrics["timeframe"]
    assert first.fingerprint == second.fingerprint


def test_trend_fingerprint_differs_when_time_bucket_differs() -> None:
    query = make_query()
    collected_at = datetime(2026, 9, 4, tzinfo=timezone.utc)
    three_points = google_mapper.map_trend_candidates(
        query,
        [make_trend_result(values=(50.0, 60.0, 80.0))],
        collected_at,
    )[0]
    four_points = google_mapper.map_trend_candidates(
        query,
        [make_trend_result(values=(50.0, 60.0, 80.0, 90.0))],
        collected_at,
    )[0]

    assert three_points.metrics["time_bucket"] == "2026-01-15T00:00:00+00:00"
    assert four_points.metrics["time_bucket"] == "2026-01-22T00:00:00+00:00"
    assert three_points.metrics["timeframe"] == four_points.metrics["timeframe"]
    assert three_points.fingerprint != four_points.fingerprint


def test_trend_fingerprint_differs_when_timeframe_differs() -> None:
    query = make_query()
    collected_at = datetime(2026, 9, 4, tzinfo=timezone.utc)
    short_window = google_mapper.map_trend_candidates(
        query,
        [make_trend_result(values=(50.0, 60.0, 80.0), timeframe="today 3-m")],
        collected_at,
    )[0]
    long_window = google_mapper.map_trend_candidates(
        query,
        [make_trend_result(values=(50.0, 60.0, 80.0), timeframe="today 12-m")],
        collected_at,
    )[0]

    assert short_window.metrics["time_bucket"] == long_window.metrics["time_bucket"]
    assert short_window.metrics["timeframe"] != long_window.metrics["timeframe"]
    assert short_window.fingerprint != long_window.fingerprint


def test_trend_empty_series_keeps_traceable_fallback_without_fabricated_bucket() -> None:
    query = make_query()
    collected_at = datetime(2026, 9, 4, tzinfo=timezone.utc)
    mapped = google_mapper.map_trend_candidates(
        query,
        [make_trend_result(values=())],
        collected_at,
    )

    assert len(mapped) == 1
    candidate = mapped[0]
    assert candidate.metrics["time_bucket"] is None
    assert candidate.fingerprint == expected_fingerprint("search_trend", "coffee")


# Real provider -> mapper chain (offline) --------------------------------


def test_suggest_provider_to_mapper_chain() -> None:
    body = json.dumps(
        ["coffee", ["coffee", "Coffee maker", "咖啡 壶"]]
    ).encode("utf-8")
    provider = GoogleSuggestProvider(
        requester=SuggestStubRequester(
            body=body,
            content_type="application/json; charset=utf-8",
        )
    )
    request = KeywordProviderRequest(
        seed_keyword="coffee",
        country_code="CN",
        language_code="zh-CN",
    )
    collected_at = datetime(2026, 9, 4, tzinfo=timezone.utc)

    suggestions = provider.discover_keywords(request)
    mapped = google_mapper.map_suggest_candidates(
        make_query(seed_query="coffee", country="CN", language="zh-CN"),
        suggestions,
        collected_at,
    )

    assert [candidate.keyword for candidate in mapped] == [
        "coffee",
        "Coffee maker",
        "咖啡 壶",
    ]
    assert mapped[1].normalized_keyword == "coffee maker"
    assert mapped[2].normalized_keyword == "咖啡 壶"
    assert mapped[2].country == "CN"
    assert mapped[2].language == "zh-CN"
    assert mapped[0].raw_data["raw_payload"] == [
        "coffee",
        ["coffee", "Coffee maker", "咖啡 壶"],
    ]
    assert mapped[0].collected_at == collected_at


def test_trends_provider_to_mapper_chain() -> None:
    responses = [
        (404, b"", "text/html; charset=utf-8", COOKIE_HEADERS),
        (200, _explore_response(), "application/json", {}),
        (200, _timeline_response(20, 40, 70), "application/json", {}),
        (
            200,
            _related_response(["coffee beans"], ["cold brew concentrate"]),
            "application/json",
            {},
        ),
    ]
    provider = GoogleTrendsProvider(requester=TrendsStubRequester(responses))
    request = KeywordProviderRequest(
        seed_keyword="coffee",
        country_code="US",
        language_code="en",
    )
    collected_at = datetime(2026, 9, 4, tzinfo=timezone.utc)

    results = provider.get_keyword_trends(["coffee"], request)
    mapped = google_mapper.map_trend_candidates(
        make_query(), results, collected_at
    )

    assert len(mapped) == 1
    first = mapped[0]
    assert first.source_type == "search_trend"
    assert first.metrics["trend_direction"] == "rising"
    assert len(first.metrics["interest_over_time"]) == 3
    assert first.metrics["related_queries"] == ["coffee beans"]
    assert first.metrics["rising_queries"] == ["cold brew concentrate"]
    assert set(first.raw_data["raw_payload"].keys()) == {
        "explore",
        "interest_over_time",
        "related_queries",
    }
    assert first.raw_data["provider"] == "google_trends"


# GoogleConnector orchestration ------------------------------------------


def test_collect_runs_suggest_and_trends_and_merges_results() -> None:
    connector = GoogleConnector(
        suggest_provider=FakeSuggestProvider(
            candidates=[make_suggestion("coffee maker"), make_suggestion("coffee grinder")]
        ),
        trends_provider=FakeTrendsProvider(results=[make_trend_result()]),
    )

    result = connector.collect(make_query())

    assert result.all_requested_sources_failed is False
    assert len(result.candidates) == 3
    assert result.candidates[0].source_type == "search_suggestion"
    assert result.candidates[2].source_type == "search_trend"
    assert result.stats.total_count == 3
    assert result.stats.by_capability == {"suggest": 2, "trends": 1}
    assert result.executed_capabilities == ["suggest", "trends"]
    assert all(
        source.status == SourceRunStatus.SUCCESS for source in result.sources
    )


def test_collect_respects_include_flags() -> None:
    trends_only = GoogleConnector(
        suggest_provider=FakeSuggestProvider(
            candidates=[make_suggestion("coffee maker")]
        ),
        trends_provider=FakeTrendsProvider(results=[make_trend_result()]),
    )

    result = trends_only.collect(
        make_query(seed_query="coffee")
        .model_copy(update={"include_suggest": False, "include_trends": True})
    )

    assert result.executed_capabilities == ["trends"]
    assert result.stats.by_capability == {"trends": 1}
    assert all(
        candidate.source_type == "search_trend" for candidate in result.candidates
    )

    suggest_only = GoogleConnector(
        suggest_provider=FakeSuggestProvider(
            candidates=[make_suggestion("coffee maker")]
        ),
        trends_provider=FakeTrendsProvider(results=[make_trend_result()]),
    )
    suggest_result = suggest_only.collect(
        make_query(seed_query="coffee")
        .model_copy(update={"include_suggest": True, "include_trends": False})
    )
    assert suggest_result.executed_capabilities == ["suggest"]
    assert suggest_result.stats.by_capability == {"suggest": 1}


def test_collect_reports_empty_provider_results_as_success() -> None:
    connector = GoogleConnector(
        suggest_provider=FakeSuggestProvider(candidates=[]),
        trends_provider=FakeTrendsProvider(results=[]),
    )

    result = connector.collect(make_query())

    assert result.all_requested_sources_failed is False
    assert result.stats.total_count == 0
    assert result.stats.by_capability == {"suggest": 0, "trends": 0}
    assert all(
        source.status == SourceRunStatus.SUCCESS for source in result.sources
    )


def test_partial_provider_failure_keeps_successful_source() -> None:
    connector = GoogleConnector(
        suggest_provider=FakeSuggestProvider(
            error=ProviderRateLimitError("Google Suggest rate limit exceeded")
        ),
        trends_provider=FakeTrendsProvider(results=[make_trend_result()]),
    )

    result = connector.collect(make_query())

    assert result.all_requested_sources_failed is False
    assert len(result.candidates) == 1
    assert result.candidates[0].source_type == "search_trend"
    assert result.stats.by_capability == {"suggest": 0, "trends": 1}
    by_capability = {source.capability: source for source in result.sources}
    assert by_capability["suggest"].status == SourceRunStatus.FAILED
    assert by_capability["suggest"].error_code == "provider_rate_limited"
    assert by_capability["trends"].status == SourceRunStatus.SUCCESS
    assert by_capability["trends"].candidate_count == 1


def test_all_providers_failed_is_flagged_and_does_not_leak_tracebacks() -> None:
    connector = GoogleConnector(
        suggest_provider=FakeSuggestProvider(
            error=ProviderTimeoutError("Google Suggest request timed out")
        ),
        trends_provider=FakeTrendsProvider(
            error=ProviderResponseError("Invalid Google Trends response")
        ),
    )

    result = connector.collect(make_query())

    assert result.all_requested_sources_failed is True
    assert result.candidates == []
    assert result.stats.total_count == 0
    by_capability = {source.capability: source for source in result.sources}
    assert by_capability["suggest"].error_code == "provider_timeout"
    assert by_capability["trends"].error_code == "provider_response_error"
    for source in result.sources:
        assert source.error_message is not None
        assert "Traceback" not in source.error_message


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (ProviderRateLimitError("rate limited"), "provider_rate_limited"),
        (ProviderTimeoutError("timed out"), "provider_timeout"),
        (ProviderRequestError("HTTP 500"), "provider_request_error"),
        (ProviderResponseError("bad payload"), "provider_response_error"),
        (ProviderNotConfiguredError("not configured"), "provider_not_configured"),
        (RuntimeError("boom"), "unexpected_error"),
    ],
)
def test_provider_errors_map_to_stable_codes(
    error: Exception,
    expected_code: str,
) -> None:
    connector = GoogleConnector(
        suggest_provider=FakeSuggestProvider(error=error),
        trends_provider=FakeTrendsProvider(results=[]),
    )

    result = connector.collect(make_query())

    failed_suggest = next(
        source for source in result.sources if source.capability == "suggest"
    )
    assert failed_suggest.status == SourceRunStatus.FAILED
    assert failed_suggest.error_code == expected_code


# Collection API ----------------------------------------------------------

COLLECT_PAYLOAD = {
    "seed_query": "coffee",
    "country": "US",
    "language": "en",
    "include_suggest": True,
    "include_trends": True,
}


def post_collect(client: TestClient, payload: dict | None = None) -> object:
    return client.post(COLLECT_URL, json=payload or COLLECT_PAYLOAD)


@pytest.fixture
def api_client():
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def install_google_connector(connector: GoogleConnector) -> None:
    """Point the API dependency at ``connector`` for the next request."""
    app.dependency_overrides[get_google_connector] = lambda: connector


def test_collect_api_returns_candidates_and_stats(api_client) -> None:
    connector = GoogleConnector(
        suggest_provider=FakeSuggestProvider(
            candidates=[make_suggestion("coffee maker"), make_suggestion("coffee grinder")]
        ),
        trends_provider=FakeTrendsProvider(results=[make_trend_result()]),
    )
    install_google_connector(connector)

    response = post_collect(api_client)

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 3
    assert body["stats"]["total_count"] == 3
    assert body["stats"]["suggest_count"] == 2
    assert body["stats"]["trend_count"] == 1
    assert body["stats"]["by_capability"] == {"suggest": 2, "trends": 1}
    assert {source["capability"] for source in body["sources"]} == {
        "suggest",
        "trends",
    }
    first = body["items"][0]
    assert first["source"] == "google"
    assert first["source_type"] == "search_suggestion"
    assert first["keyword"] == "coffee maker"
    assert HEX64.fullmatch(first["fingerprint"])


def test_collect_api_rejects_blank_seed_query(api_client) -> None:
    install_google_connector(GoogleConnector())

    response = post_collect(
        api_client,
        {
            "seed_query": "   ",
            "include_suggest": True,
            "include_trends": True,
        },
    )

    assert response.status_code == 400
    assert "seed_query must not be blank" in response.json()["detail"]


def test_collect_api_rejects_disabling_all_sources(api_client) -> None:
    install_google_connector(GoogleConnector())

    response = post_collect(
        api_client,
        {
            "seed_query": "coffee",
            "include_suggest": False,
            "include_trends": False,
        },
    )

    assert response.status_code == 400
    assert (
        "at least one of include_suggest / include_trends must be true"
        in response.json()["detail"]
    )


def test_collect_api_reports_partial_provider_failure(api_client) -> None:
    connector = GoogleConnector(
        suggest_provider=FakeSuggestProvider(
            error=ProviderRateLimitError("Google Suggest rate limit exceeded")
        ),
        trends_provider=FakeTrendsProvider(results=[make_trend_result()]),
    )
    install_google_connector(connector)

    response = post_collect(api_client)

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["stats"]["suggest_count"] == 0
    assert body["stats"]["trend_count"] == 1
    by_capability = {source["capability"]: source for source in body["sources"]}
    assert by_capability["suggest"]["status"] == "failed"
    assert by_capability["suggest"]["error_code"] == "provider_rate_limited"
    assert by_capability["trends"]["status"] == "success"


def test_collect_api_returns_502_when_all_providers_fail(api_client) -> None:
    connector = GoogleConnector(
        suggest_provider=FakeSuggestProvider(
            error=ProviderTimeoutError("Google Suggest request timed out")
        ),
        trends_provider=FakeTrendsProvider(
            error=ProviderResponseError("Invalid Google Trends response")
        ),
    )
    install_google_connector(connector)

    response = post_collect(api_client)

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["error"] == "all requested sources failed"
    by_capability = {source["capability"]: source for source in detail["sources"]}
    assert by_capability["suggest"]["error_code"] == "provider_timeout"
    assert by_capability["trends"]["error_code"] == "provider_response_error"
