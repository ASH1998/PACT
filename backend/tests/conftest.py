"""Test configuration for PACT backend.

Sets up an in-memory SQLite database before app modules are imported,
then monkey-patches the engine to use StaticPool so all connections
share the same in-memory database.
"""

import os

# Force in-memory SQLite BEFORE app modules are imported
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["PACT_INSECURE_DEMO_API"] = "true"

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Now import app modules — engine is created with the env var above
import app.database as db_mod
from app.database import Base
import app.models  # noqa: F401 — register ALL models with Base.metadata (before app import)
from app.main import app as fastapi_app  # avoid name collision with 'app' module

# Replace engine with StaticPool so all async connections share the same
# in-memory database (required for aiosqlite + in-memory)
_test_engine = create_async_engine(
    "sqlite+aiosqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)
_test_session_factory = async_sessionmaker(
    _test_engine, class_=AsyncSession, expire_on_commit=False
)

# Monkey-patch the module-level objects so all imports see the test engine
db_mod.engine = _test_engine
db_mod.async_session = _test_session_factory


@pytest.fixture
async def setup_db():
    """Create tables before each test, drop after."""
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client(setup_db):
    """Async test client."""
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
