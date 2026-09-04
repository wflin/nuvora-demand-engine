"""Stable fingerprint helpers for demand signal deduplication."""

import hashlib


def signal_fingerprint(
    *,
    source: str,
    source_type: str,
    country: str | None,
    language: str | None,
    normalized_keyword: str | None,
    timeframe: str | None = None,
    time_bucket: str | None = None,
) -> str:
    """Return the canonical SHA-256 fingerprint for a demand signal.

    Suggestion-like signals follow docs/03-DATA-MODEL.md:
    ``SHA256(source | source_type | country | language | normalized_keyword)``

    Time-varying trend signals append the Google Trends query window and the
    external source time bucket:
    ``SHA256(source | source_type | country | language | normalized_keyword |
    timeframe | time_bucket)``

    The two time parts are only appended together when a real ``time_bucket``
    is available. Callers must never fabricate a bucket for an empty or
    invalid trend series; passing ``time_bucket=None`` keeps the base rule so
    such candidates stay traceable and match the previous behaviour.
    """

    parts = [
        source,
        source_type,
        country or "",
        language or "",
        normalized_keyword or "",
    ]
    if time_bucket is not None:
        parts.append(timeframe or "")
        parts.append(time_bucket)
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


__all__ = ["signal_fingerprint"]
