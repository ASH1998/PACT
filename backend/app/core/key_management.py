"""Key management for PACT — supports multiple issuer roles."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Optional

from app.crypto import generate_keypair


# Supported key roles
KEY_ROLES = [
    "passport_issuer",
    "capability_issuer",
    "ledger_signer",
    "approval_signer",
    "agent_action",
]


class KeyManager:
    """Manages cryptographic keys for different PACT roles.

    For now uses file-based keys (same pattern as app.crypto.issuer).
    Supports separate issuer roles: passport_issuer, capability_issuer,
    ledger_signer, approval_signer.
    """

    def __init__(self, keys_dir: Optional[str] = None) -> None:
        self._keys_dir = Path(keys_dir) if keys_dir else Path(__file__).parent.parent.parent / "keys"
        self._keys: dict[str, dict[str, str]] = {}  # role -> {key_id, private_key, public_key}
        self._revoked: set[str] = set()  # revoked key_ids
        self._load_or_generate_all()

    def _key_file(self, role: str) -> Path:
        return self._keys_dir / f"{role}_keys.json"

    def _load_or_generate_all(self) -> None:
        """Load keys for all roles, generating if needed."""
        for role in KEY_ROLES:
            self._load_or_generate(role)

    def _load_or_generate(self, role: str) -> None:
        """Load or generate keys for a specific role."""
        key_file = self._key_file(role)

        if role in self._keys:
            return  # Already loaded

        if key_file.exists():
            with open(key_file) as f:
                data = json.load(f)
            self._keys[role] = {
                "key_id": data.get("key_id", f"{role}_default"),
                "private_key": data["private_key"],
                "public_key": data["public_key"],
            }
            os.chmod(key_file, 0o600)
        else:
            # Generate new keypair
            private_key, public_key = generate_keypair()
            key_id = f"{role}_{uuid.uuid4().hex[:8]}"
            self._keys[role] = {
                "key_id": key_id,
                "private_key": private_key,
                "public_key": public_key,
            }
            # Persist
            self._keys_dir.mkdir(parents=True, exist_ok=True)
            with open(key_file, "w") as f:
                json.dump(self._keys[role], f)
            os.chmod(key_file, 0o600)

    def get_key(self, role: str) -> tuple[str, str]:
        """Get (private_key, public_key) for a role.

        Raises ValueError if role is unknown or key is revoked.
        """
        if role not in self._keys:
            raise ValueError(f"Unknown key role: {role}")
        info = self._keys[role]
        if info["key_id"] in self._revoked:
            raise ValueError(f"Key for role {role} is revoked")
        return info["private_key"], info["public_key"]

    def get_key_id(self, role: str) -> str:
        """Get the current key_id for a role."""
        if role not in self._keys:
            raise ValueError(f"Unknown key role: {role}")
        return self._keys[role]["key_id"]

    def get_public_key(self, role: str) -> str:
        """Get the public key for a role."""
        if role not in self._keys:
            raise ValueError(f"Unknown key role: {role}")
        return self._keys[role]["public_key"]

    def rotate_key(self, role: str) -> str:
        """Rotate the key for a role. Returns new key_id.

        Generates a new keypair, saves to file, and returns the new key_id.
        The old key_id is NOT revoked automatically — call revoke_key() if needed.
        """
        if role not in self._keys:
            raise ValueError(f"Unknown key role: {role}")

        private_key, public_key = generate_keypair()
        new_key_id = f"{role}_{uuid.uuid4().hex[:8]}"

        self._keys[role] = {
            "key_id": new_key_id,
            "private_key": private_key,
            "public_key": public_key,
        }

        # Persist
        key_file = self._key_file(role)
        self._keys_dir.mkdir(parents=True, exist_ok=True)
        with open(key_file, "w") as f:
            json.dump(self._keys[role], f)
        os.chmod(key_file, 0o600)

        return new_key_id

    def revoke_key(self, key_id: str) -> bool:
        """Revoke a key by key_id. Returns True if found and revoked."""
        # Find which role has this key_id
        for role, info in self._keys.items():
            if info["key_id"] == key_id:
                self._revoked.add(key_id)
                return True
        return False

    def is_revoked(self, key_id: str) -> bool:
        """Check if a key_id is revoked."""
        return key_id in self._revoked

    def list_roles(self) -> list[str]:
        """List all known key roles."""
        return list(self._keys.keys())
