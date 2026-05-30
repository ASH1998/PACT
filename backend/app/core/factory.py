"""PactRuntime factory — single composition root for production flows.

All v1 routes, proxy routes, and adapters should use get_runtime() instead of
building their own service graphs.
"""
from __future__ import annotations
from typing import Optional
from app.core.runtime import PactRuntime
from app.core.key_management import KeyManager

_runtime: Optional[PactRuntime] = None
_key_manager: Optional[KeyManager] = None


def get_key_manager() -> KeyManager:
    """Get or create the global KeyManager."""
    global _key_manager
    if _key_manager is None:
        _key_manager = KeyManager()
    return _key_manager


def get_runtime() -> PactRuntime:
    """Get or create the global PactRuntime.

    Passes the KeyManager so passport and capability services use separate keys.
    """
    global _runtime
    if _runtime is None:
        km = get_key_manager()
        _runtime = PactRuntime(key_manager=km)
    return _runtime


def reset_runtime() -> None:
    """Reset the global runtime (for testing)."""
    global _runtime, _key_manager
    _runtime = None
    _key_manager = None
