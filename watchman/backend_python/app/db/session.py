# =============================================================
# app/db/session.py
# Purpose : Database engine + session factory
# Pattern : Unit of Work (session per request lifecycle)
# Replaces: Spring Boot's JPA session management
# =============================================================

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# ── Engine (one per application lifetime) ─────────────────────────────────
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # Test connection before using from pool
    pool_size=10,  # Max persistent connections
    max_overflow=20,  # Temporary connections beyond pool_size
    echo=settings.app_debug,  # Log SQL queries in development
)

# ── Session Factory ────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency: Yields a DB session per HTTP request.
    Automatically commits on success, rolls back on error, always closes.

    Usage (inject into any route or service):
        def my_endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
