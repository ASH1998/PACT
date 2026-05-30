"""Storage configuration — helper for creating async SQLAlchemy engines.

Supports both SQLite (development) and PostgreSQL (production) backends.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import create_async_engine


def create_engine_for_url(database_url: str):
    """Create an async SQLAlchemy engine for the given URL.

    Supported schemes:
    * ``sqlite+aiosqlite://`` — development / testing
    * ``postgresql+asyncpg://`` — production

    Returns a :class:`sqlalchemy.ext.asyncio.AsyncEngine`.
    """
    kwargs: dict = {"echo": False}

    if "sqlite" in database_url:
        kwargs["connect_args"] = {"check_same_thread": False}

    return create_async_engine(database_url, **kwargs)
