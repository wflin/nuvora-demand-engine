"""Offline unit tests for the Google Suggest provider.

These tests run without network access. The provider HTTP transport is
replaced with a deterministic fake requester, used only to exercise JSON
parsing, normalization, deduplication, and error handling - never to
fabricate real Google data.
"""

import io
import json
import socket
import urllib.error
import urllib.request

import pytest
from pydantic import ValidationError

from connectors.google.providers import (
    GoogleSuggestProvider,
    KeywordCandidate,
    KeywordProviderRequest,
    ProviderNotConfiguredError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderResponseError,
)
from connectors.google.providers.google_suggest import (
    SUGGEST_ENDPOINT,
    USER_AGENT,
    UrllibHttpRequester,
    normalize_keyword,
)


class StubRequester:
    """Deterministic fake HTTP transport for offline tests."""

    def __init__(
        self,
        status: int = 200,
        body: bytes = b"",
        content_type: str | None = None,
        error: Exception | None = None,
    ) -> None:
        self.status = status
        self.body = body
        self.content_type = content_type
        self.error = error
        self.calls: list[dict[str, object]] = []

    def get(
        self,
        url: str,
        headers: dict[str, str],
        timeout: float,
    ) -> tuple[int, bytes, str | None]:
        self.calls.append(
            {"url": url, "headers": dict(headers), "timeout": timeout}
        )
        if self.error is not None:
            raise self.error
        return self.status, self.body, self.content_type


def suggestion_body(*suggestions: str) -> bytes:
    return json.dumps(["query", list(suggestions)]).encode("utf-8")


def make_provider(
    body: bytes = b"",
    status: int = 200,
    content_type: str | None = None,
    error: Exception | None = None,
) -> tuple[GoogleSuggestProvider, StubRequester]:
    requester = StubRequester(
        status=status,
        body=body,
        content_type=content_type,
        error=error,
    )
    return GoogleSuggestProvider(requester=requester), requester


def test_provider_instantiable() -> None:
    provider, _ = make_provider()
    assert provider is not None
    assert GoogleSuggestProvider() is not None


def test_provider_name_and_version() -> None:
    provider, _ = make_provider()
    assert provider.name == "google_suggest"
    assert provider.version == "1"


def test_request_created_normally() -> None:
    request = KeywordProviderRequest(
        seed_keyword="coffee",
        country_code="US",
        language_code="en",
    )
    assert request.seed_keyword == "coffee"


def test_empty_seed_keyword_rejected() -> None:
    with pytest.raises(ValidationError):
        KeywordProviderRequest(seed_keyword="")


def test_url_params_are_encoded() -> None:
    from urllib.parse import parse_qs, urlparse

    provider, requester = make_provider(body=suggestion_body("coffee"))
    request = KeywordProviderRequest(
        seed_keyword="best running shoes & 2024",
        country_code="US",
        language_code="en",
    )
    provider.discover_keywords(request)
    url = requester.calls[0]["url"]
    assert isinstance(url, str)
    assert url.startswith(SUGGEST_ENDPOINT + "?")
    assert " " not in url
    parsed = parse_qs(urlparse(url).query)
    assert parsed["q"] == ["best running shoes & 2024"]
    assert parsed["hl"] == ["en"]
    assert parsed["gl"] == ["us"]
    assert parsed["client"] == ["firefox"]


def test_country_code_is_passed_and_lowercased() -> None:
    provider, requester = make_provider(body=suggestion_body("coffee"))
    request = KeywordProviderRequest(
        seed_keyword="coffee",
        country_code="GB",
        language_code="en",
    )
    provider.discover_keywords(request)
    url = requester.calls[0]["url"]
    assert "gl=gb" in url


def test_language_code_is_passed() -> None:
    provider, requester = make_provider(body=suggestion_body("咖啡"))
    request = KeywordProviderRequest(
        seed_keyword="咖啡",
        country_code="CN",
        language_code="zh-CN",
    )
    provider.discover_keywords(request)
    url = requester.calls[0]["url"]
    assert "hl=zh-CN" in url
    assert "gl=cn" in url


def test_requester_receives_user_agent_and_timeout() -> None:
    provider, requester = make_provider(body=suggestion_body("coffee"))
    request = KeywordProviderRequest(seed_keyword="coffee")
    provider.discover_keywords(request)
    headers = requester.calls[0]["headers"]
    assert headers == {"User-Agent": USER_AGENT}
    assert requester.calls[0]["timeout"] == 5.0


def test_normal_json_parsing() -> None:
    provider, _ = make_provider(
        body=suggestion_body("coffee", "coffee shops near me")
    )
    request = KeywordProviderRequest(seed_keyword="coffee")
    candidates = provider.discover_keywords(request)
    assert [c.keyword_text for c in candidates] == [
        "coffee",
        "coffee shops near me",
    ]


def test_multiple_suggestions_preserve_order() -> None:
    provider, _ = make_provider(
        body=suggestion_body("a", "b", "c", "d")
    )
    request = KeywordProviderRequest(seed_keyword="seed")
    candidates = provider.discover_keywords(request)
    assert [c.keyword_text for c in candidates] == ["a", "b", "c", "d"]


def test_duplicate_suggestions_are_deduplicated() -> None:
    provider, _ = make_provider(
        body=suggestion_body("abc", "abc", "abc", "def", "abc")
    )
    request = KeywordProviderRequest(seed_keyword="abc")
    candidates = provider.discover_keywords(request)
    assert [c.keyword_text for c in candidates] == ["abc", "def"]


def test_empty_and_whitespace_suggestions_are_skipped() -> None:
    provider, _ = make_provider(
        body=suggestion_body("", "   ", "real", "  ")
    )
    request = KeywordProviderRequest(seed_keyword="real")
    candidates = provider.discover_keywords(request)
    assert [c.keyword_text for c in candidates] == ["real"]


def test_empty_suggestion_list_returns_empty_result() -> None:
    provider, _ = make_provider(body=suggestion_body())
    request = KeywordProviderRequest(seed_keyword="nothing")
    assert provider.discover_keywords(request) == []


def test_malformed_json_raises_response_error() -> None:
    provider, _ = make_provider(body=b"this is not json")
    request = KeywordProviderRequest(seed_keyword="coffee")
    with pytest.raises(ProviderResponseError):
        provider.discover_keywords(request)


@pytest.mark.parametrize(
    "body",
    [
        b'["only-one"]',
        b'{"not": "a list"}',
        b'["q", "not-a-list"]',
        b'["q", [123, 456]]',
    ],
)
def test_unexpected_response_structure_raises_response_error(body: bytes) -> None:
    provider, _ = make_provider(body=body)
    request = KeywordProviderRequest(seed_keyword="coffee")
    with pytest.raises(ProviderResponseError):
        provider.discover_keywords(request)


def test_timeout_error_is_propagated() -> None:
    provider, _ = make_provider(
        error=ProviderRequestError("Google Suggest request timed out")
    )
    request = KeywordProviderRequest(seed_keyword="coffee")
    with pytest.raises(ProviderRequestError):
        provider.discover_keywords(request)


def test_http_4xx_raises_request_error() -> None:
    provider, _ = make_provider(status=404, body=b"not found")
    request = KeywordProviderRequest(seed_keyword="coffee")
    with pytest.raises(ProviderRequestError) as exc_info:
        provider.discover_keywords(request)
    assert str(exc_info.value) == "Google Suggest returned HTTP 404"


def test_http_5xx_raises_request_error() -> None:
    provider, _ = make_provider(status=503, body=b"unavailable")
    request = KeywordProviderRequest(seed_keyword="coffee")
    with pytest.raises(ProviderRequestError) as exc_info:
        provider.discover_keywords(request)
    assert str(exc_info.value) == "Google Suggest returned HTTP 503"


def test_http_429_raises_rate_limit_error() -> None:
    provider, _ = make_provider(status=429, body=b"too many requests")
    request = KeywordProviderRequest(seed_keyword="coffee")
    with pytest.raises(ProviderRateLimitError):
        provider.discover_keywords(request)


def test_keyword_candidate_normalization() -> None:
    provider, _ = make_provider(body=suggestion_body(" Best Running Shoes "))
    request = KeywordProviderRequest(seed_keyword="shoes")
    candidates = provider.discover_keywords(request)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert isinstance(candidate, KeywordCandidate)
    assert candidate.keyword_text == " Best Running Shoes "
    assert candidate.normalized_keyword == "best running shoes"
    assert candidate.source_type == "provider"
    assert candidate.provider == "google_suggest"


def test_chinese_keywords_preserved() -> None:
    provider, _ = make_provider(
        body=suggestion_body("上海 股票", "上海股票开户")
    )
    request = KeywordProviderRequest(
        seed_keyword="上海 股票",
        country_code="CN",
        language_code="zh-CN",
    )
    candidates = provider.discover_keywords(request)
    assert [c.keyword_text for c in candidates] == ["上海 股票", "上海股票开户"]
    assert candidates[0].normalized_keyword == "上海 股票"
    assert candidates[0].normalized_keyword != "上海股票"
    assert candidates[1].normalized_keyword == "上海股票开户"


def test_unicode_keywords_preserved() -> None:
    provider, _ = make_provider(body=suggestion_body("Café au lait"))
    request = KeywordProviderRequest(seed_keyword="cafe")
    candidates = provider.discover_keywords(request)
    assert candidates[0].keyword_text == "Café au lait"
    assert candidates[0].normalized_keyword == "café au lait"


def test_normalize_keyword_pure_function() -> None:
    assert normalize_keyword("  Best   Running  Shoes ") == "best running shoes"
    assert normalize_keyword("上海 股票") == "上海 股票"
    assert normalize_keyword("Café") == "café"
    assert normalize_keyword("a\t\nb") == "a b"


def test_provider_error_messages_do_not_leak_details() -> None:
    provider, _ = make_provider(body=b"garbage")
    request = KeywordProviderRequest(seed_keyword="coffee")
    with pytest.raises(ProviderResponseError) as exc_info:
        provider.discover_keywords(request)
    message = str(exc_info.value)
    assert message == "Invalid Google Suggest response"
    assert "coffee" not in message
    assert SUGGEST_ENDPOINT not in message

    provider500, _ = make_provider(status=500, body=b"internal error body")
    with pytest.raises(ProviderRequestError) as exc_info:
        provider500.discover_keywords(request)
    assert str(exc_info.value) == "Google Suggest returned HTTP 500"


def test_get_keyword_metrics_raises_not_configured() -> None:
    provider, _ = make_provider()
    request = KeywordProviderRequest(seed_keyword="coffee")
    with pytest.raises(ProviderNotConfiguredError):
        provider.get_keyword_metrics(["coffee"], request)


def test_response_with_utf8_content_type_is_decoded() -> None:
    body = suggestion_body("coffee", "coffee table")
    provider, _ = make_provider(
        body=body,
        content_type="text/javascript; charset=utf-8",
    )
    request = KeywordProviderRequest(seed_keyword="coffee")
    candidates = provider.discover_keywords(request)
    assert [c.keyword_text for c in candidates] == ["coffee", "coffee table"]


def test_response_with_gb2312_content_type_is_decoded() -> None:
    payload = json.dumps(
        ["咖啡", ["咖啡云", "咖啡"]],
        ensure_ascii=False,
    ).encode("gb2312")
    provider, _ = make_provider(
        body=payload,
        content_type="text/javascript; charset=GB2312",
    )
    request = KeywordProviderRequest(
        seed_keyword="咖啡",
        country_code="CN",
        language_code="zh-CN",
    )
    candidates = provider.discover_keywords(request)
    assert [c.keyword_text for c in candidates] == ["咖啡云", "咖啡"]
    assert candidates[0].normalized_keyword == "咖啡云"


def test_response_with_unknown_charset_raises_response_error() -> None:
    provider, _ = make_provider(
        body=suggestion_body("coffee"),
        content_type="text/javascript; charset=x-unknown",
    )
    request = KeywordProviderRequest(seed_keyword="coffee")
    with pytest.raises(ProviderResponseError):
        provider.discover_keywords(request)


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


def test_urllib_requester_returns_http_error_status_and_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_http_error(*args: object, **kwargs: object) -> None:
        raise urllib.error.HTTPError(
            "https://example.test", 429, "Too Many Requests", {}, io.BytesIO(b"{}")
        )

    monkeypatch.setattr(urllib.request, "urlopen", raise_http_error)
    status, body, content_type = UrllibHttpRequester().get(
        "https://example.test",
        {"User-Agent": USER_AGENT},
        5.0,
    )
    assert status == 429
    assert body == b"{}"
    assert content_type is None
