"""Google Trends keyword trend provider.

Fetches real relative-interest time series from the public Google Trends
JSON API (trends.google.com/trends/api) and converts them into the P1-007
``KeywordTrend`` contract. This provider only produces relative interest
(0-100) and related/rising queries; it never fabricates search volume, CPC,
or competition data.

The provider drives the same public, undocumented JSON API that the
trends.google.com web app uses (the same capability exposed by the
non-official ``pytrends`` client). Google may change this backend at any
time; this provider fails loudly with a :class:`ProviderError` instead of
inventing data, and can be replaced by another Trend provider without
touching callers.
"""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Protocol

from .base import KeywordProvider
from .exceptions import (
    ProviderError,
    ProviderNotConfiguredError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from .models import (
    KeywordProviderRequest,
    KeywordTrend,
    KeywordTrendResult,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://trends.google.com/trends"
COOKIE_PAGE_URL = f"{BASE_URL}/explore/"
EXPLORE_ENDPOINT = f"{BASE_URL}/api/explore"
INTEREST_OVER_TIME_ENDPOINT = f"{BASE_URL}/api/widgetdata/multiline"
RELATED_QUERIES_ENDPOINT = f"{BASE_URL}/api/widgetdata/relatedsearches"

USER_AGENT = "Google-Keyword-Research/1.0"
DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_TIMEFRAME = "today 12-m"
DEFAULT_TZ_OFFSET_MINUTES = -480
XSSI_PREFIX = b")]}'"


class HttpRequester(Protocol):
    """Minimal HTTP GET/POST transport used by :class:`GoogleTrendsProvider`.

    Implementations raise :class:`ProviderRequestError` for transport-level
    failures (DNS, connection, timeout) and return
    ``(status, body, content type, headers)`` for completed HTTP exchanges.
    ``headers`` maps lowercase header names to values; repeated headers are
    joined with newlines.
    """

    def get(
        self,
        url: str,
        headers: Mapping[str, str],
        timeout: float,
    ) -> tuple[int, bytes, str | None, Mapping[str, str]]:
        """Perform a GET request and return the normalized response."""

    def post(
        self,
        url: str,
        headers: Mapping[str, str],
        timeout: float,
    ) -> tuple[int, bytes, str | None, Mapping[str, str]]:
        """Perform a POST request and return the normalized response."""


class UrllibHttpRequester:
    """Default :class:`HttpRequester` backed by the Python standard library."""

    def get(
        self,
        url: str,
        headers: Mapping[str, str],
        timeout: float,
    ) -> tuple[int, bytes, str | None, Mapping[str, str]]:
        return self._request(url, headers, timeout, method="GET")

    def post(
        self,
        url: str,
        headers: Mapping[str, str],
        timeout: float,
    ) -> tuple[int, bytes, str | None, Mapping[str, str]]:
        return self._request(url, headers, timeout, method="POST")

    def _request(
        self,
        url: str,
        headers: Mapping[str, str],
        timeout: float,
        method: str,
    ) -> tuple[int, bytes, str | None, Mapping[str, str]]:
        request = urllib.request.Request(url, headers=dict(headers), method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return (
                    response.status,
                    response.read(),
                    response.headers.get("Content-Type"),
                    _headers_to_mapping(response.headers),
                )
        except urllib.error.HTTPError as exc:
            # HTTPError is a subclass of URLError, so it must be caught first.
            return (
                exc.code,
                exc.read(),
                exc.headers.get("Content-Type"),
                _headers_to_mapping(exc.headers),
            )
        except TimeoutError as exc:
            raise ProviderTimeoutError("Google Trends request timed out") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise ProviderRequestError("Google Trends request failed") from exc


def _headers_to_mapping(headers: Mapping[str, str]) -> dict[str, str]:
    """Lowercase header names and merge repeated headers with newlines."""

    merged: dict[str, str] = {}
    for name, value in headers.items():
        key = name.lower()
        if key in merged:
            merged[key] = f"{merged[key]}\n{value}"
        else:
            merged[key] = value
    return merged


def extract_nid_cookie(headers: Mapping[str, str] | None) -> str | None:
    """Return the NID cookie value from response headers, if present."""

    if not headers:
        return None
    raw = headers.get("set-cookie")
    if not raw:
        return None
    for cookie_line in raw.split("\n"):
        for part in cookie_line.split(";"):
            name, separator, value = part.strip().partition("=")
            if separator and name.lower() == "nid" and value:
                return value
    return None


def compute_trend_direction(points: list[KeywordTrend]) -> str | None:
    """Derive a coarse direction from a real relative-interest series.

    Compares the average of the second half with the first half and returns
    ``"rising"``, ``"falling"``, or ``"stable"``. Returns ``None`` when there
    are not enough points. This is derived from observed data only and never
    fabricates values.
    """

    if len(points) < 2:
        return None
    midpoint = len(points) // 2
    first_half = points[:midpoint]
    second_half = points[midpoint:]
    first_average = sum(point.value for point in first_half) / len(first_half)
    second_average = sum(point.value for point in second_half) / len(second_half)
    if second_average - first_average > 2.0:
        return "rising"
    if first_average - second_average > 2.0:
        return "falling"
    return "stable"


class GoogleTrendsProvider(KeywordProvider):
    """Real Google Trends trend provider.

    ``get_keyword_trends`` fetches, for each keyword, the explore widget
    tokens and then the interest-over-time series plus related/rising
    queries. Requests are sequential and bounded by ``timeout``. Keyword
    discovery and demand metrics are not supported: those methods raise
    :class:`ProviderNotConfiguredError` instead of fabricating data.
    """

    name = "google_trends"
    version = "1"

    def __init__(
        self,
        requester: HttpRequester | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._requester = requester if requester is not None else UrllibHttpRequester()
        self._timeout = timeout

    def discover_keywords(
        self,
        request: KeywordProviderRequest,
    ) -> list:
        """Trends do not provide suggestions; never fabricate any."""
        raise ProviderNotConfiguredError(
            "Google Trends does not provide keyword suggestions"
        )

    def get_keyword_metrics(
        self,
        keywords: list[str],
        request: KeywordProviderRequest,
    ) -> list:
        """Trends do not provide search volume/CPC/competition; never fabricate."""
        raise ProviderNotConfiguredError(
            "Google Trends does not provide keyword metrics"
        )

    def get_keyword_trends(
        self,
        keywords: list[str],
        request: KeywordProviderRequest,
        timeframe: str = DEFAULT_TIMEFRAME,
    ) -> list[KeywordTrendResult]:
        """Return real Google Trends relative-interest data for ``keywords``.

        Empty and whitespace-only keywords are skipped and duplicates are
        removed (first occurrence wins). Each unique keyword is fetched
        sequentially. The returned series keeps Google's original
        chronological order and contains no duplicate time points.
        """

        unique_keywords = _unique_keywords(keywords)
        if not unique_keywords:
            return []
        cookie = self._fetch_cookie(request)
        results = []
        for keyword in unique_keywords:
            results.append(
                self._fetch_keyword_trend(keyword, request, timeframe, cookie)
            )
        return results

    def _fetch_cookie(self, request: KeywordProviderRequest) -> dict[str, str]:
        """Fetch the NID cookie Google Trends requires before API calls."""

        url = f"{COOKIE_PAGE_URL}?geo={request.country_code.upper()}"
        status, _body, _content_type, headers = self._request(
            "GET",
            url,
            {},
            request.language_code,
        )
        if status == 429:
            raise ProviderRateLimitError("Google Trends rate limit exceeded")
        nid = extract_nid_cookie(headers)
        if status >= 500 or nid is None:
            raise ProviderRequestError("Google Trends cookie request failed")
        return {"NID": nid}

    def _fetch_keyword_trend(
        self,
        keyword: str,
        request: KeywordProviderRequest,
        timeframe: str,
        cookie: Mapping[str, str],
    ) -> KeywordTrendResult:
        widgets, explore_payload = self._fetch_widgets(
            keyword, request, timeframe, cookie
        )
        timeseries_widget = _find_widget(widgets, "TIMESERIES")
        if timeseries_widget is None:
            raise ProviderResponseError("Invalid Google Trends response")
        related_widget = _find_related_queries_widget(widgets)
        points, timeline_payload = self._fetch_interest_over_time(
            keyword, request, timeseries_widget, cookie
        )
        related_queries: list[str] = []
        rising_queries: list[str] = []
        related_payload: dict[str, object] | None = None
        if related_widget is not None:
            (
                related_queries,
                rising_queries,
                related_payload,
            ) = self._fetch_related_queries(
                request, related_widget, cookie
            )
        return KeywordTrendResult(
            keyword=keyword,
            country_code=request.country_code,
            language_code=request.language_code,
            timeframe=timeframe,
            trend_series=points,
            trend_direction=compute_trend_direction(points),
            related_queries=related_queries,
            rising_queries=rising_queries,
            retrieved_at=datetime.now(timezone.utc),
            source=self.name,
            provider_version=self.version,
            raw_payload={
                "explore": explore_payload,
                "interest_over_time": timeline_payload,
                "related_queries": related_payload,
            },
        )

    def _fetch_widgets(
        self,
        keyword: str,
        request: KeywordProviderRequest,
        timeframe: str,
        cookie: Mapping[str, str],
    ) -> tuple[list[object], dict[str, object]]:
        url = self._build_explore_url(keyword, request, timeframe)
        status, body, _content_type, _headers = self._request(
            "POST",
            url,
            cookie,
            request.language_code,
        )
        self._raise_for_status(status)
        payload = self._parse_json(body)
        if not isinstance(payload, dict):
            raise ProviderResponseError("Invalid Google Trends response")
        widgets = payload.get("widgets")
        if not isinstance(widgets, list):
            raise ProviderResponseError("Invalid Google Trends response")
        return widgets, payload

    def _fetch_interest_over_time(
        self,
        keyword: str,
        request: KeywordProviderRequest,
        widget: Mapping[str, object],
        cookie: Mapping[str, str],
    ) -> tuple[list[KeywordTrend], dict[str, object]]:
        url = self._build_widget_url(INTEREST_OVER_TIME_ENDPOINT, widget, cookie)
        status, body, _content_type, _headers = self._request(
            "GET",
            url,
            cookie,
            request.language_code,
        )
        self._raise_for_status(status)
        payload = self._parse_json(body)
        timeline = self._get_timeline_data(payload)
        points: list[KeywordTrend] = []
        if not isinstance(payload, dict):
            raise ProviderResponseError("Invalid Google Trends response")
        seen_times: set[datetime] = set()
        for entry in timeline:
            point = self._parse_timeline_point(entry, keyword, request)
            if point.time in seen_times:
                continue
            seen_times.add(point.time)
            points.append(point)
        return points, payload

    def _fetch_related_queries(
        self,
        request: KeywordProviderRequest,
        widget: Mapping[str, object],
        cookie: Mapping[str, str],
    ) -> tuple[list[str], list[str], dict[str, object] | None]:
        url = self._build_widget_url(RELATED_QUERIES_ENDPOINT, widget, cookie)
        status, body, _content_type, _headers = self._request(
            "GET",
            url,
            cookie,
            request.language_code,
        )
        self._raise_for_status(status)
        payload = self._parse_json(body)
        if not isinstance(payload, dict):
            raise ProviderResponseError("Invalid Google Trends response")
        ranked_lists = self._get_ranked_lists(payload)
        if not ranked_lists:
            return [], [], payload
        rising_queries = (
            self._parse_ranked_queries(ranked_lists[1])
            if len(ranked_lists) > 1
            else []
        )
        return (
            self._parse_ranked_queries(ranked_lists[0]),
            rising_queries,
            payload,
        )

    def _request(
        self,
        method: str,
        url: str,
        cookie: Mapping[str, str],
        language: str,
    ) -> tuple[int, bytes, str | None, Mapping[str, str]]:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": language,
        }
        if cookie:
            headers["Cookie"] = "; ".join(
                f"{name}={value}" for name, value in cookie.items()
            )
        logger.info("Google Trends %s request started", method)
        try:
            if method == "POST":
                result = self._requester.post(url, headers, self._timeout)
            else:
                result = self._requester.get(url, headers, self._timeout)
        except ProviderError as exc:
            logger.warning("Google Trends request failed: %s", type(exc).__name__)
            raise
        logger.info("Google Trends request completed: status=%s", result[0])
        return result

    def _build_explore_url(
        self,
        keyword: str,
        request: KeywordProviderRequest,
        timeframe: str,
    ) -> str:
        payload = {
            "comparisonItem": [
                {
                    "keyword": keyword,
                    "geo": request.country_code.upper(),
                    "time": timeframe,
                }
            ],
            "category": 0,
            "property": "",
        }
        params = urllib.parse.urlencode(
            {
                "hl": request.language_code,
                "tz": DEFAULT_TZ_OFFSET_MINUTES,
                "req": json.dumps(payload),
            }
        )
        return f"{EXPLORE_ENDPOINT}?{params}"

    def _build_widget_url(
        self,
        endpoint: str,
        widget: Mapping[str, object],
        cookie: Mapping[str, str],
    ) -> str:
        if "request" not in widget or "token" not in widget:
            raise ProviderResponseError("Invalid Google Trends response")
        params = urllib.parse.urlencode(
            {
                "req": json.dumps(widget["request"]),
                "token": widget["token"],
                "tz": DEFAULT_TZ_OFFSET_MINUTES,
            }
        )
        return f"{endpoint}?{params}"

    def _raise_for_status(self, status: int) -> None:
        if status == 429:
            raise ProviderRateLimitError("Google Trends rate limit exceeded")
        if status >= 400:
            raise ProviderRequestError(f"Google Trends returned HTTP {status}")

    def _parse_json(self, body: bytes) -> object:
        if body.startswith(XSSI_PREFIX):
            # Google prefixes responses with an XSSI guard such as ")]}'\n"
            # or ")]}',\n"; strip the guard and any following punctuation.
            body = body[len(XSSI_PREFIX) :].lstrip(b",\n")
        try:
            return json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ProviderResponseError(
                "Invalid Google Trends response"
            ) from None

    def _get_timeline_data(self, payload: object) -> list[object]:
        if not isinstance(payload, dict):
            raise ProviderResponseError("Invalid Google Trends response")
        default = payload.get("default")
        if not isinstance(default, dict):
            raise ProviderResponseError("Invalid Google Trends response")
        timeline = default.get("timelineData")
        if not isinstance(timeline, list):
            raise ProviderResponseError("Invalid Google Trends response")
        return timeline

    def _get_ranked_lists(self, payload: object) -> list[object]:
        if not isinstance(payload, dict):
            raise ProviderResponseError("Invalid Google Trends response")
        default = payload.get("default")
        if not isinstance(default, dict):
            raise ProviderResponseError("Invalid Google Trends response")
        ranked = default.get("rankedList")
        if not isinstance(ranked, list):
            raise ProviderResponseError("Invalid Google Trends response")
        return ranked

    def _parse_timeline_point(
        self,
        entry: object,
        keyword: str,
        request: KeywordProviderRequest,
    ) -> KeywordTrend:
        if not isinstance(entry, dict):
            raise ProviderResponseError("Invalid Google Trends response")
        return KeywordTrend(
            keyword=keyword,
            time=self._parse_timestamp(entry.get("time")),
            value=self._parse_value(entry.get("value")),
            country_code=request.country_code,
            language_code=request.language_code,
            provider=self.name,
        )

    def _parse_timestamp(self, raw: object) -> datetime:
        if isinstance(raw, str) and raw.isdigit():
            raw = int(raw)
        if not isinstance(raw, int) or isinstance(raw, bool):
            raise ProviderResponseError("Invalid Google Trends response")
        try:
            return datetime.fromtimestamp(raw, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            raise ProviderResponseError(
                "Invalid Google Trends response"
            ) from None

    def _parse_value(self, raw: object) -> float:
        if isinstance(raw, list):
            raw = raw[0] if raw else None
        if isinstance(raw, str) and raw.strip().isdigit():
            raw = int(raw.strip())
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            raise ProviderResponseError("Invalid Google Trends response")
        return float(raw)

    def _parse_ranked_queries(self, ranked_list: object) -> list[str]:
        if not isinstance(ranked_list, dict):
            raise ProviderResponseError("Invalid Google Trends response")
        items = ranked_list.get("rankedKeyword")
        if not isinstance(items, list):
            return []
        queries: list[str] = []
        seen: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                raise ProviderResponseError("Invalid Google Trends response")
            query = item.get("query")
            if not isinstance(query, str) or query == "" or query.isspace():
                continue
            if query in seen:
                continue
            seen.add(query)
            queries.append(query)
        return queries


def _unique_keywords(keywords: list[str]) -> list[str]:
    """Return non-empty keywords, deduplicated in first-seen order."""

    seen: set[str] = set()
    unique: list[str] = []
    for keyword in keywords:
        if keyword == "" or keyword.isspace():
            continue
        if keyword in seen:
            continue
        seen.add(keyword)
        unique.append(keyword)
    return unique


def _find_widget(
    widgets: list[object],
    widget_id: str,
) -> Mapping[str, object] | None:
    for widget in widgets:
        if isinstance(widget, dict) and widget.get("id") == widget_id:
            return widget
    return None


def _find_related_queries_widget(widgets: list[object]) -> Mapping[str, object] | None:
    for widget in widgets:
        if isinstance(widget, dict) and isinstance(widget.get("id"), str):
            if widget["id"].startswith("RELATED_QUERIES"):
                return widget
    return None
