"""Database engine and session management."""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all PACT models."""

    pass


async def get_db() -> AsyncSession:
    """Dependency that yields a database session."""
    async with async_session() as session:
        yield session


# Lightweight additive migrations for existing SQLite DBs (no Alembic yet).
# create_all() creates missing tables but never adds columns to existing ones,
# so each new column is added idempotently here. Each runs in its own
# transaction so an "already exists" failure doesn't poison the others.
_COLUMN_MIGRATIONS = [
    ("actions", "result_json", "TEXT DEFAULT NULL"),
    ("intents", "resource_scope_json", "TEXT NOT NULL DEFAULT '{}'"),
]


async def init_db() -> None:
    """Create all tables and apply additive column migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    for table, column, coldef in _COLUMN_MIGRATIONS:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {coldef}"))
        except Exception:
            pass  # column already exists


async def close_db() -> None:
    """Dispose the engine."""
    await engine.dispose()
