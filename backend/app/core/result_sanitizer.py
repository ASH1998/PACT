"""Strip sensitive fields from tool results before they are persisted.

The backend stores only the *outcome* of a tool call (status, type, path,
findings counts), never the content of secret/chat material. Keys listed in
``SENSITIVE_KEYS`` are removed recursively from any result dict before it is
written to ``actions.result_json``.
"""

from typing import Any

# Keys that must never be persisted to the database.
SENSITIVE_KEYS = frozenset(
    {
        "content_redacted",  # redacted file body (e.g. .env contents)
        "secret_findings",   # per-secret key names, digests, lengths
    }
)


def strip_sensitive_fields(value: Any) -> Any:
    """Recursively drop SENSITIVE_KEYS from dicts/lists. Returns a copy."""
    if isinstance(value, dict):
        return {
            k: strip_sensitive_fields(v)
            for k, v in value.items()
            if k not in SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [strip_sensitive_fields(item) for item in value]
    return value
