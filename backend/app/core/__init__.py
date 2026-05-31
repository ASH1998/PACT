"""PACT Core — production module for agent security protocol.

Use lazy imports to avoid circular dependency with app.tools:
    app.core.__init__ -> app.core.runtime -> app.services.gateway -> app.tools -> app.core.registry

Instead, import specific modules directly:
    from app.core.runtime import PactRuntime
    from app.core.registry import ToolRegistry, get_default_registry
    from app.core.key_management import KeyManager
    from app.core.policy_config import PolicyConfig
"""

__all__ = [
    "PactRuntime",
    "ToolRegistry",
    "get_default_registry",
    "KeyManager",
    "PolicyConfig",
    "StorageInterface",
    "PolicyInterface",
    "ToolRegistryInterface",
    "ToolMetadata",
    "SideEffect",
]
