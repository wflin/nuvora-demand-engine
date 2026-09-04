"""SQLAlchemy engine and session factory.

DATABASE_URL is read from the unified application settings
(see ``app.core.settings`` and ``.env.example``).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import settings

engine = create_engine(
    settings.database_url,
    connect_args={"connect_timeout": settings.database_connect_timeout},
)

SessionLocal = sessionmaker(bind=engine)

__all__ = ["Session", "SessionLocal", "engine"]
