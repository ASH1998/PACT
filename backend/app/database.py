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


async def init_db() -> None:
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # SQLite migration: add result_json column to actions if missing
        try:
            await conn.execute(text("ALTER TABLE actions ADD COLUMN result_json TEXT DEFAULT NULL"))
        except Exception:
            pass  # column already exists


async def close_db() -> None:
    """Dispose the engine."""
    await engine.dispose()
