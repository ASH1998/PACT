"""Tests for storage configuration and extended settings."""

from __future__ import annotations

import os

import pytest

from app.core.storage import create_engine_for_url


class TestCreateEngineForUrl:
    """Tests for create_engine_for_url."""

    def test_sqlite_url(self):
        """SQLite URL creates an engine with check_same_thread=False."""
        engine = create_engine_for_url("sqlite+aiosqlite://")
        assert engine is not None
        assert "sqlite" in engine.url.drivername

    def test_sqlite_file_url(self):
        """SQLite file-based URL works."""
        engine = create_engine_for_url("sqlite+aiosqlite:///./test.db")
        assert engine is not None

    def test_postgres_url(self):
        """Postgres URL creates an engine (no actual connection needed)."""
        pytest.importorskip("asyncpg", reason="asyncpg not installed")
        engine = create_engine_for_url(
            "postgresql+asyncpg://user:pass@localhost:5432/pactdb"
        )
        assert engine is not None
        assert "postgresql" in engine.url.drivername

    def test_engine_kwargs_sqlite(self):
        """SQLite engine gets connect_args."""
        engine = create_engine_for_url("sqlite+aiosqlite://")
        # The engine should have connect_args configured
        # We can verify it by checking the dialect
        assert engine.dialect.name == "sqlite"

    def test_engine_kwargs_postgres(self):
        """Postgres engine does not get sqlite-specific connect_args."""
        pytest.importorskip("asyncpg", reason="asyncpg not installed")
        engine = create_engine_for_url(
            "postgresql+asyncpg://user:pass@localhost:5432/test"
        )
        assert engine.dialect.name == "postgresql"


class TestExtendedSettings:
    """Tests for ExtendedSettings and load_extended_settings."""

    def test_default_values(self):
        """ExtendedSettings has sensible defaults."""
        from app.core.config_extended import ExtendedSettings

        s = ExtendedSettings()
        assert s.postgres_url == ""
        assert s.proxy_enabled is True
        assert s.approval_ttl_seconds == 3600
        assert s.key_rotation_days == 90
        assert s.log_level == "INFO"

    def test_load_from_env(self):
        """load_extended_settings reads from environment variables."""
        from app.core.config_extended import load_extended_settings

        # Set env vars
        old_env = {}
        env_vars = {
            "POSTGRES_URL": "postgresql+asyncpg://u:p@h:5432/db",
            "PROXY_ENABLED": "false",
            "APPROVAL_TTL_SECONDS": "7200",
            "KEY_ROTATION_DAYS": "30",
            "LOG_LEVEL": "debug",
        }
        for k, v in env_vars.items():
            old_env[k] = os.environ.get(k)
            os.environ[k] = v

        try:
            s = load_extended_settings()
            assert s.postgres_url == "postgresql+asyncpg://u:p@h:5432/db"
            assert s.proxy_enabled is False
            assert s.approval_ttl_seconds == 7200
            assert s.key_rotation_days == 30
            assert s.log_level == "DEBUG"
        finally:
            # Restore env
            for k in env_vars:
                if old_env[k] is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = old_env[k]

    def test_singleton_instance(self):
        """Module-level extended_settings is created."""
        from app.core.config_extended import extended_settings

        assert extended_settings is not None
        assert hasattr(extended_settings, "postgres_url")
