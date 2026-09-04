"""Offline unit tests for the Google Trends provider.

These tests run without network access. The provider HTTP transport is
replaced with a deterministic fake requester, used only to exercise request
construction, JSON parsing, normalization, deduplication, ordering, and
error handling - never to fabricate real Google data.
"""

import io
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import pytest

from connectors.google.providers import (
    GoogleTrendsProvider,
    KeywordProviderRequest,
    KeywordTrend,
    KeywordTrendResult,
    ProviderNotConfiguredError,
    ProviderRateLimitError,
    ProviderRegistry,
    ProviderRequestError,
    ProviderResponseError,
    StubKeywordProvider,
)
from connectors.google.providers.google_trends import (
    COOKIE_PAGE_URL,
    DEFAULT_TIMEFRAME,
    DEFAULT_TIMEOUT_SECONDS,
    EXPLORE_ENDPOINT,
    INTEREST_OVER_TIME_ENDPOINT,
    RELATED_QUERIES_ENDPOINT,
    USER_AGENT,
    UrllibHttpRequester,
    extract_nid_cookie,
)

XSSI = b")]}'\n"

COOKIE_HEADERS = {
    "set-cookie": (
        "NID=511=abc123; Expires=Wed, 01 Jan 2027 00:00:00 GMT; "
        "Path=/; Domain=.google.com; HttpOnly"
    )
}


def xssi(payload: object) -> bytes:
    return XSSI + json.dumps(payload).encode("utf-8")


def explore_response(*, timeseries: bool = True, related: bool = True) -> bytes:
    widgets = []
    if timeseries:
        widgets.append(
            {
                "id": "TIMESERIES",
                "request": {"comparisonItem": [], "resolution": "WEEK"},
                "token": "ts-token",
            }
        )
    if related:
        widgets.append(
            {
                "id": "RELATED_QUERIES",
                "request": {"comparisonItem": [], "metric": ["TOP", "RISING"]},
                "token": "rq-token",
            }
        )
    return xssi({"widgets": widgets})


def timeline_response(*values: int) -> bytes:
    timeline = [
        {
            "time": str(1700000000 + index * 604800),
            "formattedTime": f"week-{index}",
            "value": [value],
        }
        for index, value in enumerate(values)
    ]
    return xssi({"default": {"timelineData": timeline}})


def related_response(top: list[str], rising: list[str]) -> bytes:
    ranked = [
        {"rankedKeyword": [{"query": query, "value": index} for index, query in enumerate(top)]},
        {"rankedKeyword": [{"query": query, "value": "+100%"} for query in rising]},
    ]
    return xssi({"default": {"rankedList": ranked}})


class StubRequester:
    """Deterministic fake HTTP transport for offline tests."""

    def __init__(
        self,
        responses: list[tuple[int, bytes, str | None, dict[str, str]]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.responses = list(responses or [])
        self.error = error
        self.calls: list[dict[str, object]] = []

    def get(
        self,
        url: str,
        headers: dict[str, str],
        timeout: float,
    ) -> tuple[int, bytes, str | None, dict[str, str]]:
        self.calls.append(
            {"method": "GET", "url": url, "headers": dict(headers), "timeout": timeout}
        )
        if self.error is not None:
            raise self.error
        return self.responses.pop(0)

    def post(
        self,
        url: str,
        headers: dict[str, str],
        timeout: float,
    ) -> tuple[int, bytes, str | None, dict[str, str]]:
        self.calls.append(
            {"method": "POST", "url": url, "headers": dict(headers), "timeout": timeout}
        )
        if self.error is not None:
            raise self.error
        return self.responses.pop(0)


def make_provider(
    responses: list[tuple[int, bytes, str | None, dict[str, str]]] | None = None,
    error: Exception | None = None,
) -> tuple[GoogleTrendsProvider, StubRequester]:
    requester = StubRequester(responses=responses, error=error)
    return GoogleTrendsProvider(requester=requester), requester


def standard_responses(
    *values: int,
    top: list[str] | None = None,
    rising: list[str] | None = None,
) -> list[tuple[int, bytes, str | None, dict[str, str]]]:
    return [
        (404, b"", "text/html; charset=utf-8", COOKIE_HEADERS),
        (200, explore_response(), "application/json", {}),
        (200, timeline_response(*values), "application/json", {}),
        (200, related_response(top or [], rising or []), "application/json", {}),
    ]


def request_for(
    keyword: str = "coffee",
    country_code: str = "US",
    language_code: str = "en",
) -> KeywordProviderRequest:
    return KeywordProviderRequest(
        seed_keyword=keyword,
        country_code=country_code,
        language_code=language_code,
    )


def test_provider_instantiable() -> None:
    provider, _ = make_provider()
    assert provider is not None
    assert GoogleTrendsProvider() is not None


def test_provider_name_and_version() -> None:
    provider, _ = make_provider()
    assert provider.name == "google_trends"
    assert provider.version == "1"


def test_default_timeout_and_timeframe() -> None:
    assert DEFAULT_TIMEOUT_SECONDS == 5.0
    assert DEFAULT_TIMEFRAME == "today 12-m"


def test_discover_keywords_raises_not_configured() -> None:
    provider, _ = make_provider()
    with pytest.raises(ProviderNotConfiguredError):
        provider.discover_keywords(request_for())


def test_get_keyword_metrics_raises_not_configured() -> None:
    provider, _ = make_provider()
    with pytest.raises(ProviderNotConfiguredError):
        provider.get_keyword_metrics(["coffee"], request_for())


def test_default_interface_raises_not_configured() -> None:
    for provider in (StubKeywordProvider(),):
        with pytest.raises(ProviderNotConfiguredError):
            provider.get_keyword_trends(["coffee"], request_for())


def test_empty_keywords_returns_empty_list_without_requests() -> None:
    provider, requester = make_provider()
    results = provider.get_keyword_trends([], request_for())
    assert results == []
    assert requester.calls == []


def test_keywords_are_deduped_and_whitespace_filtered() -> None:
    provider, requester = make_provider(responses=standard_responses(50, 60))
    results = provider.get_keyword_trends(
        ["coffee", "coffee", "   ", "coffee"],
        request_for(),
    )
    assert len(results) == 1
    assert results[0].keyword == "coffee"
    explore_calls = [call for call in requester.calls if call["method"] == "POST"]
    assert len(explore_calls) == 1


def test_request_flow_order_and_headers() -> None:
    provider, requester = make_provider(responses=standard_responses(50))
    provider.get_keyword_trends(["coffee"], request_for())
    methods = [call["method"] for call in requester.calls]
    assert methods == ["GET", "POST", "GET", "GET"]
    assert str(requester.calls[0]["url"]).startswith(COOKIE_PAGE_URL + "?geo=US")
    assert str(requester.calls[1]["url"]).startswith(EXPLORE_ENDPOINT + "?")
    assert str(requester.calls[2]["url"]).startswith(INTEREST_OVER_TIME_ENDPOINT + "?")
    assert str(requester.calls[3]["url"]).startswith(RELATED_QUERIES_ENDPOINT + "?")
    for call in requester.calls:
        headers = call["headers"]
        assert isinstance(headers, dict)
        assert headers["User-Agent"] == USER_AGENT
        assert call["timeout"] == 5.0
    assert "Cookie" not in requester.calls[0]["headers"]
    for call in requester.calls[1:]:
        assert call["headers"]["Cookie"] == "NID=511=abc123"


def test_explore_url_is_encoded_and_contains_expected_params() -> None:
    from urllib.parse import parse_qs, urlparse

    provider, requester = make_provider(responses=standard_responses(50))
    provider.get_keyword_trends(
        ["best coffee & beans"],
        request_for(country_code="US", language_code="en"),
    )
    url = str(requester.calls[1]["url"])
    assert " " not in url
    parsed = parse_qs(urlparse(url).query)
    assert parsed["hl"] == ["en"]
    assert parsed["tz"] == ["-480"]
    req = json.loads(parsed["req"][0])
    assert req["comparisonItem"][0]["keyword"] == "best coffee & beans"
    assert req["comparisonItem"][0]["geo"] == "US"
    assert req["comparisonItem"][0]["time"] == "today 12-m"


def test_explore_geo_is_uppercased_and_language_passed() -> None:
    provider, requester = make_provider(responses=standard_responses(50))
    provider.get_keyword_trends(
        ["coffee"],
        request_for(country_code="cn", language_code="zh-CN"),
    )
    url = str(requester.calls[1]["url"])
    assert "hl=zh-CN" in url
    req = json.loads(urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["req"][0])
    assert req["comparisonItem"][0]["geo"] == "CN"


def test_timeframe_is_passed_through() -> None:
    provider, requester = make_provider(responses=standard_responses(50))
    provider.get_keyword_trends(["coffee"], request_for(), timeframe="now 7-d")
    url = str(requester.calls[1]["url"])
    req = json.loads(urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["req"][0])
    assert req["comparisonItem"][0]["time"] == "now 7-d"


def test_widget_urls_contain_req_token_and_tz() -> None:
    provider, requester = make_provider(responses=standard_responses(50))
    provider.get_keyword_trends(["coffee"], request_for())
    for index in (2, 3):
        parsed = urllib.parse.parse_qs(
            urllib.parse.urlparse(str(requester.calls[index]["url"])).query
        )
        assert "req" in parsed
        assert parsed["token"] == ["ts-token" if index == 2 else "rq-token"]
        assert parsed["tz"] == ["-480"]


def test_timeline_parsed_in_original_order_as_utc() -> None:
    provider, _ = make_provider(responses=standard_responses(10, 20, 30))
    results = provider.get_keyword_trends(["coffee"], request_for())
    series = results[0].trend_series
    assert len(series) == 3
    assert [point.value for point in series] == [10.0, 20.0, 30.0]
    assert [point.time for point in series] == sorted(point.time for point in series)
    assert all(point.time.tzinfo == timezone.utc for point in series)
    assert series[0].keyword == "coffee"
    assert series[0].country_code == "US"
    assert series[0].language_code == "en"
    assert series[0].provider == "google_trends"


def test_timeline_duplicate_time_points_removed_preserving_order() -> None:
    timeline = xssi(
        {
            "default": {
                "timelineData": [
                    {"time": "1700000000", "value": [10]},
                    {"time": "1700000000", "value": [99]},
                    {"time": "1700000600", "value": [20]},
                ]
            }
        }
    )
    responses = [
        (404, b"", "text/html", COOKIE_HEADERS),
        (200, explore_response(), "application/json", {}),
        (200, timeline, "application/json", {}),
        (200, related_response([], []), "application/json", {}),
    ]
    provider, _ = make_provider(responses=responses)
    series = provider.get_keyword_trends(["coffee"], request_for())[0].trend_series
    assert [point.value for point in series] == [10.0, 20.0]


def test_related_queries_parsed_without_values() -> None:
    provider, _ = make_provider(
        responses=standard_responses(50, top=["coffee near me", "coffee shop"], rising=["coffee beans"])
    )
    result = provider.get_keyword_trends(["coffee"], request_for())[0]
    assert result.related_queries == ["coffee near me", "coffee shop"]
    assert result.rising_queries == ["coffee beans"]


def test_related_queries_skip_empty_and_dedup() -> None:
    body = xssi(
        {
            "default": {
                "rankedList": [
                    {
                        "rankedKeyword": [
                            {"query": "a"},
                            {"query": "a"},
                            {"query": ""},
                            {"query": "  "},
                            {"query": None},
                        ]
                    },
                    {
                        "rankedKeyword": [
                            {"query": "b"},
                            {"query": "b"},
                        ]
                    },
                ]
            }
        }
    )
    responses = [
        (404, b"", "text/html", COOKIE_HEADERS),
        (200, explore_response(), "application/json", {}),
        (200, timeline_response(50), "application/json", {}),
        (200, body, "application/json", {}),
    ]
    provider, _ = make_provider(responses=responses)
    result = provider.get_keyword_trends(["coffee"], request_for())[0]
    assert result.related_queries == ["a"]
    assert result.rising_queries == ["b"]


def test_missing_related_widget_returns_empty_queries() -> None:
    responses = [
        (404, b"", "text/html", COOKIE_HEADERS),
        (200, explore_response(related=False), "application/json", {}),
        (200, timeline_response(50), "application/json", {}),
    ]
    provider, _ = make_provider(responses=responses)
    result = provider.get_keyword_trends(["coffee"], request_for())[0]
    assert result.related_queries == []
    assert result.rising_queries == []


def test_missing_timeseries_widget_raises_response_error() -> None:
    responses = [
        (404, b"", "text/html", COOKIE_HEADERS),
        (200, explore_response(timeseries=False), "application/json", {}),
    ]
    provider, _ = make_provider(responses=responses)
    with pytest.raises(ProviderResponseError):
        provider.get_keyword_trends(["coffee"], request_for())


def test_widget_missing_request_or_token_raises_response_error() -> None:
    broken_widgets = xssi(
        {"widgets": [{"id": "TIMESERIES", "token": "ts-token"}]}
    )
    responses = [
        (404, b"", "text/html", COOKIE_HEADERS),
        (200, broken_widgets, "application/json", {}),
    ]
    provider, _ = make_provider(responses=responses)
    with pytest.raises(ProviderResponseError):
        provider.get_keyword_trends(["coffee"], request_for())


def test_trend_direction_computed_from_real_series() -> None:
    provider, _ = make_provider(responses=standard_responses(10, 20, 30, 40, 50, 60))
    assert provider.get_keyword_trends(["coffee"], request_for())[0].trend_direction == "rising"

    provider, _ = make_provider(responses=standard_responses(60, 50, 40, 30, 20, 10))
    assert provider.get_keyword_trends(["coffee"], request_for())[0].trend_direction == "falling"

    provider, _ = make_provider(responses=standard_responses(30, 31, 30, 31, 30, 31))
    assert provider.get_keyword_trends(["coffee"], request_for())[0].trend_direction == "stable"

    provider, _ = make_provider(responses=standard_responses(50))
    assert provider.get_keyword_trends(["coffee"], request_for())[0].trend_direction is None


def test_result_metadata() -> None:
    provider, _ = make_provider(responses=standard_responses(50))
    result = provider.get_keyword_trends(["coffee"], request_for())[0]
    assert result.keyword == "coffee"
    assert result.country_code == "US"
    assert result.language_code == "en"
    assert result.timeframe == "today 12-m"
    assert result.source == "google_trends"
    assert result.provider_version == "1"
    assert result.retrieved_at.tzinfo == timezone.utc


def test_http_429_raises_rate_limit() -> None:
    responses = [
        (404, b"", "text/html", COOKIE_HEADERS),
        (429, b"", "application/json", {}),
    ]
    provider, _ = make_provider(responses=responses)
    with pytest.raises(ProviderRateLimitError):
        provider.get_keyword_trends(["coffee"], request_for())


def test_http_500_raises_request_error() -> None:
    responses = [
        (404, b"", "text/html", COOKIE_HEADERS),
        (500, b"internal error", "text/html", {}),
    ]
    provider, _ = make_provider(responses=responses)
    with pytest.raises(ProviderRequestError) as exc_info:
        provider.get_keyword_trends(["coffee"], request_for())
    assert str(exc_info.value) == "Google Trends returned HTTP 500"


def test_http_400_raises_request_error() -> None:
    responses = [
        (404, b"", "text/html", COOKIE_HEADERS),
        (400, b"", "text/html", {}),
    ]
    provider, _ = make_provider(responses=responses)
    with pytest.raises(ProviderRequestError):
        provider.get_keyword_trends(["coffee"], request_for())


def test_invalid_json_raises_response_error() -> None:
    responses = [
        (404, b"", "text/html", COOKIE_HEADERS),
        (200, b"garbage", "application/json", {}),
    ]
    provider, _ = make_provider(responses=responses)
    with pytest.raises(ProviderResponseError):
        provider.get_keyword_trends(["coffee"], request_for())


def test_xssi_prefix_with_comma_is_stripped() -> None:
    timeline = b")]}',\n" + json.dumps(
        {"default": {"timelineData": [{"time": "1700000000", "value": [42]}]}}
    ).encode("utf-8")
    responses = [
        (404, b"", "text/html", COOKIE_HEADERS),
        (200, explore_response(), "application/json", {}),
        (200, timeline, "application/json", {}),
        (200, related_response([], []), "application/json", {}),
    ]
    provider, _ = make_provider(responses=responses)
    series = provider.get_keyword_trends(["coffee"], request_for())[0].trend_series
    assert [point.value for point in series] == [42.0]


def test_unexpected_widget_structure_raises_response_error() -> None:
    responses = [
        (404, b"", "text/html", COOKIE_HEADERS),
        (200, xssi({"widgets": "nope"}), "application/json", {}),
    ]
    provider, _ = make_provider(responses=responses)
    with pytest.raises(ProviderResponseError):
        provider.get_keyword_trends(["coffee"], request_for())


def test_unexpected_timeline_structure_raises_response_error() -> None:
    responses = [
        (404, b"", "text/html", COOKIE_HEADERS),
        (200, explore_response(), "application/json", {}),
        (200, xssi({"default": {"timelineData": "nope"}}), "application/json", {}),
    ]
    provider, _ = make_provider(responses=responses)
    with pytest.raises(ProviderResponseError):
        provider.get_keyword_trends(["coffee"], request_for())


def test_error_messages_do_not_leak_details() -> None:
    provider, _ = make_provider(
        responses=[
            (404, b"", "text/html", COOKIE_HEADERS),
            (200, explore_response(), "application/json", {}),
            (200, timeline_response(50), "application/json", {}),
            (200, xssi({"default": {"rankedList": "nope"}}), "application/json", {}),
        ]
    )
    with pytest.raises(ProviderResponseError) as exc_info:
        provider.get_keyword_trends(["coffee"], request_for())
    message = str(exc_info.value)
    assert message == "Invalid Google Trends response"
    assert "coffee" not in message
    assert EXPLORE_ENDPOINT not in message


def test_timeout_from_requester_propagates() -> None:
    error = ProviderRequestError("Google Trends request timed out")
    provider, _ = make_provider(error=error)
    with pytest.raises(ProviderRequestError) as exc_info:
        provider.get_keyword_trends(["coffee"], request_for())
    assert "timed out" in str(exc_info.value)


def test_urllib_requester_maps_timeout_to_request_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_timeout(*args: object, **kwargs: object) -> None:
        raise socket.timeout("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", raise_timeout)
    with pytest.raises(ProviderRequestError) as exc_info:
        UrllibHttpRequester().get(
            "https://example.test",
            {"User-Agent": USER_AGENT},
            5.0,
        )
    assert "timed out" in str(exc_info.value)


def test_urllib_requester_maps_dns_error_to_request_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_url_error(*args: object, **kwargs: object) -> None:
        raise urllib.error.URLError("name resolution failed")

    monkeypatch.setattr(urllib.request, "urlopen", raise_url_error)
    with pytest.raises(ProviderRequestError):
        UrllibHttpRequester().get(
            "https://example.test",
            {"User-Agent": USER_AGENT},
            5.0,
        )


def test_urllib_requester_returns_http_error_status_and_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_http_error(*args: object, **kwargs: object) -> None:
        raise urllib.error.HTTPError(
            "https://example.test",
            404,
            "Not Found",
            {"Set-Cookie": "NID=511=xyz; Path=/"},
            io.BytesIO(b"{}"),
        )

    monkeypatch.setattr(urllib.request, "urlopen", raise_http_error)
    status, body, content_type, headers = UrllibHttpRequester().get(
        "https://example.test",
        {"User-Agent": USER_AGENT},
        5.0,
    )
    assert status == 404
    assert body == b"{}"
    assert content_type is None
    assert extract_nid_cookie(headers) == "511=xyz"


def test_extract_nid_cookie_pure_function() -> None:
    assert extract_nid_cookie(None) is None
    assert extract_nid_cookie({}) is None
    assert (
        extract_nid_cookie({"set-cookie": "SOCS=CAI; NID=511=abc; Path=/"})
        == "511=abc"
    )
    assert (
        extract_nid_cookie({"set-cookie": "NID=511=abc\nOTHER=1"}) == "511=abc"
    )


def test_registry_accepts_google_trends_provider() -> None:
    registry = ProviderRegistry()
    registry.register("google_trends", GoogleTrendsProvider())
    assert registry.get("google_trends").name == "google_trends"


def test_keyword_trend_model_minimal_fields() -> None:
    point = KeywordTrend(
        keyword="coffee",
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        value=42.5,
        country_code="US",
        language_code="en",
        provider="google_trends",
    )
    assert point.value == 42.5
    assert point.provider == "google_trends"


def test_keyword_trend_result_model_minimal_fields() -> None:
    point = KeywordTrend(
        keyword="coffee",
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        value=42.0,
        country_code="US",
        provider="google_trends",
    )
    result = KeywordTrendResult(
        keyword="coffee",
        country_code="US",
        timeframe="today 12-m",
        trend_series=[point],
        retrieved_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        source="google_trends",
        provider_version="1",
    )
    assert result.related_queries == []
    assert result.rising_queries == []
    assert result.trend_direction is None
