"""Google connector query contract."""

from connectors.base import SourceQuery


class GoogleQuery(SourceQuery):
    """Collection request accepted by the Google connector."""

    include_suggest: bool = True
    include_trends: bool = True


__all__ = ["GoogleQuery"]
