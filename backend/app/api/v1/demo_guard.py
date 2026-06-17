"""Guards for v1 endpoints that are intentionally demo-only today."""

from fastapi import HTTPException

from app.config import settings


def require_insecure_demo_api() -> None:
    """Require explicit opt-in before exposing demo authority endpoints."""
    if not settings.allow_insecure_demo_api:
        raise HTTPException(
            status_code=403,
            detail=(
                "This endpoint is demo-only because it can create authority without "
                "production authentication. Set PACT_INSECURE_DEMO_API=true for "
                "local demos, or use a production authority service."
            ),
        )
