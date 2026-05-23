"""Canonical JSON serialization and hashing for PACT protocol."""

import hashlib
import json


def canonical_json(payload: dict) -> bytes:
    """Produce deterministic JSON bytes: sorted keys, no whitespace, UTF-8."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def hash_payload(payload: dict) -> str:
    """SHA-256 hash of canonicalized dict. Returns 'sha256:hex' string."""
    data = canonical_json(payload)
    return "sha256:" + hashlib.sha256(data).hexdigest()


def hash_bytes(data: bytes) -> str:
    """SHA-256 hash of raw bytes. Returns 'sha256:hex' string."""
    return "sha256:" + hashlib.sha256(data).hexdigest()
