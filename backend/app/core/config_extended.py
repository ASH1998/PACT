"""Extended application settings for production deployments.

This module adds production-oriented fields to the base settings **without**
modifying ``app.config`` directly.  Use :func:`load_extended_settings` to
create an instance populated from environment variables.
"""

from __future__ import annotations

import os

from pydantic import BaseModel


class ExtendedSettings(BaseModel):
    """Additional settings for production / operational features."""

    # Database — production Postgres URL (optional; falls back to SQLite)
    postgres_url: str = ""

    # Proxy / gateway
    proxy_enabled: bool = True

    # Approval workflow
    approval_ttl_seconds: int = 3600

    # Crypto
    key_rotation_days: int = 90

    # Observability
    log_level: str = "INFO"


def load_extended_settings() -> ExtendedSettings:
    """Load extended settings from environment variables with sensible defaults."""
    return ExtendedSettings(
        postgres_url=os.getenv("POSTGRES_URL", ""),
        proxy_enabled=os.getenv("PROXY_ENABLED", "true").lower() in ("true", "1", "yes"),
        approval_ttl_seconds=int(os.getenv("APPROVAL_TTL_SECONDS", "3600")),
        key_rotation_days=int(os.getenv("KEY_ROTATION_DAYS", "90")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )


extended_settings = load_extended_settings()
