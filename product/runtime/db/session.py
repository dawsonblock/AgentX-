"""Database session management for runtime."""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

# Default to SQLite for local development, override with env var for production
DATABASE_URL = os.getenv(
    "RUNTIME_DATABASE_URL",
    "postgresql://product:product@localhost:5432/product_runtime"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db() -> Session:
    """Get a database session with automatic cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session() -> Session:
    """Get a new database session."""
    return SessionLocal()
