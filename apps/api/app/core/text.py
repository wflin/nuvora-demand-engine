"""Canonical text normalization helpers used across the engine."""


def normalize_keyword(keyword: str) -> str:
    """Return a deterministic normalized form for dedup/matching.

    Strategy: trim, lowercase and collapse runs of whitespace to a single
    space. Intentionally simple; no NLP in this phase. Chinese text with
    spaces is preserved: whitespace runs collapse to a single space and are
    never removed between characters.
    """

    return " ".join(keyword.strip().lower().split())


def normalize_text(text: str | None) -> str | None:
    """Normalize arbitrary short text with the same rules as keywords."""
    if text is None:
        return None
    return normalize_keyword(text)


__all__ = ["normalize_keyword", "normalize_text"]
