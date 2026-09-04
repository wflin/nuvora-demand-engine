"""Google source connector.

Contains all Google-specific collection code: the ported Google Suggest and
Google Trends providers, the Google mapper, and the :class:`GoogleConnector`
that turns provider output into unified ``DemandSignalCandidate`` records.
"""

from .google_connector import GoogleConnector

__all__ = ["GoogleConnector"]
