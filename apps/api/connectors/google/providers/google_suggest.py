"""Google Suggest keyword suggestion provider.

Fetches real keyword suggestions from the public Google Suggest
(autocomplete) endpoint and converts them into the P1-007
``KeywordCandidate`` contract. This provider only produces suggestions; it
never fabricates search volume, CPC, or competition data.
"""

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
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
from .models import KeywordCandidate, KeywordProviderRequest

logger = logging.getLogger(__name__)

SUGGEST_ENDPOINT = "https://suggestqueries.google.com/complete/search"
USER_AGENT = "Google-Keyword-Research/1.0"
DEFAULT_TIMEOUT_SECONDS = 5.0


class HttpRequester(Protocol):
    """Minimal HTTP GET transport used by :class:`GoogleSuggestProvider`.

    Implementations raise :class:`ProviderRequestError` for transport-level
    failures (DNS, connection, timeout) and return
    ``(status, body, content type)`` for completed HTTP exchanges.
    """

    def get(
        self,
        url: str,
        headers: Mapping[str, str],
        timeout: float,
    ) -> tuple[int, bytes, str | None]:
        """Return ``(status code, response body, content type)``."""


class UrllibHttpRequester:
    """Default :class:`HttpRequester` backed by the Python standard library."""

    def get(
        self,
        url: str,
        headers: Mapping[str, str],
        timeout: float,
    ) -> tuple[int, bytes, str | None]:
        request = urllib.request.Request(url, headers=dict(headers), method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return (
                    response.status,
                    response.read(),
                    response.headers.get("Content-Type"),
                )
        except urllib.error.HTTPError as exc:
            # HTTPError is a subclass of URLError, so it must be caught first.
            return exc.code, exc.read(), exc.headers.get("Content-Type")
        except TimeoutError as exc:
            raise ProviderTimeoutError(
                "Google Suggest request timed out"
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise ProviderRequestError(
                "Google Suggest request failed"
            ) from exc


def normalize_keyword(keyword: str) -> str:
    """Return a deterministic normalized form for dedup/matching.

    Mirrors the project convention (trim, lowercase, collapse whitespace)
    without coupling the provider layer to the SQLAlchemy models. Chinese text
    with spaces is preserved: whitespace runs collapse to a single space and
    are never removed between characters.
    """

    return " ".join(keyword.strip().lower().split())


class GoogleSuggestProvider(KeywordProvider):
    """Keyword suggestion provider backed by the real Google Suggest endpoint.

    ``discover_keywords`` issues exactly one HTTP request for the seed
    keyword and returns real suggestions as :class:`KeywordCandidate`
    objects. Metrics are not supported: :meth:`get_keyword_metrics` always
    raises :class:`ProviderNotConfiguredError` instead of fabricating data.
    """

    name = "google_suggest"
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
    ) -> list[KeywordCandidate]:
        """Return real Google Suggest keyword candidates for ``request``."""
        url = self._build_url(request)
        status, body, content_type = self._fetch(url)
        if status == 429:
            raise ProviderRateLimitError(
                "Google Suggest rate limit exceeded"
            )
        if status >= 400:
            raise ProviderRequestError(
                f"Google Suggest returned HTTP {status}"
            )
        suggestions, raw_payload = self._parse_suggestions(body, content_type)
        return [
            KeywordCandidate(
                keyword_text=suggestion,
                normalized_keyword=normalize_keyword(suggestion),
                source_type="provider",
                provider=self.name,
                raw_payload=raw_payload,
            )
            for suggestion in suggestions
        ]

    def get_keyword_metrics(
        self,
        keywords: list[str],
        request: KeywordProviderRequest,
    ) -> list:
        """Suggestions do not include metrics; never fabricate them."""
        raise ProviderNotConfiguredError(
            "Google Suggest does not provide keyword metrics"
        )

    def _build_url(self, request: KeywordProviderRequest) -> str:
        """Build the suggest URL with all request values URL-encoded.

        ``hl`` uses the language code as-is (for example ``en`` or
        ``zh-CN``); ``gl`` uses the lowercased country code (for example
        ``us`` or ``gb``) because Google Suggest expects it lowercased.
        """

        query = urllib.parse.urlencode(
            {
                "client": "firefox",
                "hl": request.language_code,
                "gl": request.country_code.lower(),
                "q": request.seed_keyword,
            }
        )
        return f"{SUGGEST_ENDPOINT}?{query}"

    def _fetch(self, url: str) -> tuple[int, bytes, str | None]:
        logger.info("Google Suggest request started")
        try:
            status, body, content_type = self._requester.get(
                url,
                {"User-Agent": USER_AGENT},
                self._timeout,
            )
        except ProviderError as exc:
            logger.warning("Google Suggest request failed: %s", type(exc).__name__)
            raise
        logger.info("Google Suggest request completed: status=%s", status)
        return status, body, content_type

    def _parse_suggestions(
        self,
        body: bytes,
        content_type: str | None,
    ) -> list[str]:
        """Decode and validate the suggest response.

        Returns ``(cleaned suggestions, raw payload)`` where ``raw_payload``
        is the full decoded Google response so callers can retain the original
        data for audit and re-parsing.

        The response is a JSON array whose second element is the suggestion
        list. The body is decoded with the charset declared in
        ``Content-Type`` (Google uses UTF-8 for most locales and GB2312 for
        ``zh-CN``); when no charset is declared, UTF-8 is assumed. Empty and
        whitespace-only strings are dropped, duplicates are removed, and the
        first-seen order is preserved. The original suggestion text is kept
        unchanged.
        """

        try:
            payload = json.loads(self._decode_body(body, content_type))
        except json.JSONDecodeError:
            raise ProviderResponseError(
                "Invalid Google Suggest response"
            ) from None

        if not isinstance(payload, list) or len(payload) < 2:
            raise ProviderResponseError("Invalid Google Suggest response")
        suggestions = payload[1]
        if not isinstance(suggestions, list):
            raise ProviderResponseError("Invalid Google Suggest response")

        cleaned: list[str] = []
        seen: set[str] = set()
        for item in suggestions:
            if not isinstance(item, str):
                raise ProviderResponseError("Invalid Google Suggest response")
            text = item
            if text == "" or text.isspace():
                continue
            if text in seen:
                continue
            seen.add(text)
            cleaned.append(text)
        return cleaned, payload

    def _decode_body(self, body: bytes, content_type: str | None) -> str:
        """Decode the response body using the charset from Content-Type."""

        charset = None
        if content_type:
            match = re.search(r"charset=([\w-]+)", content_type, re.IGNORECASE)
            if match:
                charset = match.group(1)
        if charset:
            try:
                return body.decode(charset)
            except (LookupError, UnicodeDecodeError):
                raise ProviderResponseError(
                    "Invalid Google Suggest response"
                ) from None
        try:
            return body.decode("utf-8")
        except UnicodeDecodeError:
            raise ProviderResponseError(
                "Invalid Google Suggest response"
            ) from None
