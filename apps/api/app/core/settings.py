"""Unified application configuration.

All runtime configuration is read from environment variables so the same
code runs unchanged in local development, tests and deployments. The
available variables are documented in the repository ``.env.example``.
"""

import os

DEFAULT_CORS_ORIGINS = ["http://localhost:3000"]
DEFAULT_DATABASE_CONNECT_TIMEOUT = 5


def _comma_separated(value: str | None) -> list[str]:
    """Split a comma-separated environment value into a trimmed list."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    """Read-only application settings loaded from the environment."""

    def __init__(self) -> None:
        self.app_env: str = os.environ.get("APP_ENV", "development")
        self.log_level: str = os.environ.get("LOG_LEVEL", "INFO").upper()
        configured_origins = _comma_separated(os.environ.get("CORS_ORIGINS"))
        self.cors_origins: list[str] = configured_origins or DEFAULT_CORS_ORIGINS

        self.database_url: str = os.environ.get("DATABASE_URL") or ""
        if not self.database_url:
            raise RuntimeError(
                "DATABASE_URL is not set. Copy .env.example to .env or export "
                "DATABASE_URL."
            )

        raw_timeout = os.environ.get(
            "DB_CONNECT_TIMEOUT", str(DEFAULT_DATABASE_CONNECT_TIMEOUT)
        )
        try:
            self.database_connect_timeout = int(raw_timeout)
        except ValueError:
            raise RuntimeError("DB_CONNECT_TIMEOUT must be an integer") from None
        if self.database_connect_timeout <= 0:
            raise RuntimeError("DB_CONNECT_TIMEOUT must be a positive integer")


settings = Settings()

__all__ = ["Settings", "settings"]
