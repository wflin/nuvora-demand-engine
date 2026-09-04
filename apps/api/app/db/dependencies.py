"""FastAPI dependency for request-scoped SQLAlchemy sessions."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Yield a session for the current request and close it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
