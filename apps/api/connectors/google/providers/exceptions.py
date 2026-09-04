"""Provider-specific exception hierarchy.

Every provider error inherits from :class:`ProviderError`. Exception messages
must never include API keys, database credentials, connection strings, or
Authorization headers.
"""


class ProviderError(Exception):
    """Base class for all keyword data provider errors."""


class ProviderNotConfiguredError(ProviderError):
    """Raised when a provider has not been configured."""


class ProviderAuthenticationError(ProviderError):
    """Raised when authentication with the external data source fails."""


class ProviderRateLimitError(ProviderError):
    """Raised when the external data source rate limit is exceeded."""


class ProviderRequestError(ProviderError):
    """Raised when a request to the external data source fails."""


class ProviderTimeoutError(ProviderRequestError):
    """Raised when a request to the external data source times out."""


class ProviderResponseError(ProviderError):
    """Raised when a response from the external data source is invalid."""
