"""Application configuration loaded from environment."""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

_repo_root = Path(__file__).resolve().parents[2]
_backend_root = Path(__file__).resolve().parents[1]
load_dotenv(_repo_root / ".env", override=False)
load_dotenv(_backend_root / ".env", override=False)


class Settings(BaseModel):
    """PACT application settings."""

    # Database
    database_url: str = "sqlite+aiosqlite:///./pact.db"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # LLM (optional, for agent runtime)
    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    # Crypto
    passport_issuer_key_path: str = "./keys/issuer.key"

    # Demo/development controls
    allow_insecure_demo_api: bool = False

    # Paths
    base_dir: Path = Path(__file__).parent.parent


def load_settings() -> Settings:
    """Load settings from environment variables with fallback defaults."""
    def env_bool(name: str, default: bool = False) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./pact.db"),
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        llm_provider=os.getenv("LLM_PROVIDER", "openai"),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        passport_issuer_key_path=os.getenv("PASSPORT_ISSUER_KEY_PATH", "./keys/issuer.key"),
        allow_insecure_demo_api=env_bool("PACT_INSECURE_DEMO_API", False),
    )


settings = load_settings()
